import email.message
import io
import json
import re
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_data as fd  # noqa: E402


def headers(**kv):
    m = email.message.Message()
    for k, v in kv.items():
        m[k.replace("_", "-")] = v
    return m


class Resp:
    def __init__(self, body, hdrs=None):
        self.body, self.headers = body, hdrs or headers(ratelimit='"500-in-10min"; r=400; t=300')

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ok(data, **h):
    return Resp(json.dumps({"status": "success", "data": data}).encode(), headers(**h) if h else None)


def http_error(code, **h):
    return urllib.error.HTTPError("u", code, "err", headers(**h), io.BytesIO(b"{}"))


class Scripted:
    """Opener that replays a fixed sequence of responses/exceptions and records URLs."""

    def __init__(self, *items):
        self.items, self.urls = list(items), []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeAPI:
    """In-memory MCSR API: leaderboards, paginated match lists, match details."""

    def __init__(self, seasons, bad_matches=(), bad_users=()):
        self.seasons = seasons  # {season: {uuid: [match ids, newest first]}}
        self.bad_matches, self.bad_users = set(bad_matches), set(bad_users)
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if m := re.search(r"/leaderboard\?season=(\d+)", url):
            users = [{"uuid": u, "nickname": f"nick-{u}"} for u in self.seasons[int(m[1])]]
            return ok({"users": users})
        if m := re.search(r"/users/(\w+)/matches\?season=(\d+)&count=(\d+).*?(?:&before=(\d+))?$", url):
            if m[1] in self.bad_users:
                raise http_error(404)
            ids = self.seasons[int(m[2])][m[1]]
            if m[4]:
                ids = [i for i in ids if i < int(m[4])]
            return ok([{"id": i} for i in ids[: int(m[3])]])
        if m := re.search(r"/matches/(\d+)$", url):
            if int(m[1]) in self.bad_matches:
                raise http_error(400)
            return ok({"id": int(m[1]), "timelines": []})
        raise AssertionError(url)


def client(opener, sleeps=None):
    return fd.Client(opener=opener, sleep=(sleeps.append if sleeps is not None else lambda s: None))


# ---------------------------------------------------------------- rate limits / HTTP

def test_parse_ratelimit():
    """Extracts remaining requests and reset seconds; None when header is absent."""
    assert fd.parse_ratelimit(headers(ratelimit='"500-in-10min"; r=12; t=345')) == (12, 345)
    assert fd.parse_ratelimit(headers()) is None


def test_retry_after_precedence():
    """429 wait uses Retry-After first, then rate-limit reset, then a 60s default."""
    assert fd.retry_after(headers(Retry_After="7")) == 7
    assert fd.retry_after(headers(ratelimit="r=0; t=30")) == 31
    assert fd.retry_after(headers()) == 60
    assert fd.retry_after(None) == 60


def test_get_returns_data_and_counts_requests():
    """A successful response returns the `data` payload and increments the request counter."""
    c = client(Scripted(ok({"x": 1})))
    assert c.get("/p") == {"x": 1}
    assert c.requests == 1


def test_get_sleeps_when_window_exhausted():
    """When the rate-limit header shows <=1 remaining, the client waits out the window."""
    sleeps = []
    client(Scripted(ok(1, ratelimit="r=1; t=200")), sleeps).get("/p")
    assert sleeps == [201]


def test_get_waits_and_retries_on_429():
    """HTTP 429 triggers a wait of the advertised duration, then a successful retry."""
    sleeps = []
    assert client(Scripted(http_error(429, Retry_After="42"), ok("y")), sleeps).get("/p") == "y"
    assert sleeps == [42]


def test_get_backs_off_on_server_and_network_errors():
    """5xx, network errors and bad JSON are retried with exponential backoff."""
    sleeps = []
    bad_json = Resp(b"not json")
    c = client(Scripted(http_error(503), ConnectionResetError(), bad_json, ok("z")), sleeps)
    assert c.get("/p") == "z"
    assert sleeps == [5, 10, 20]


def test_backoff_is_capped(monkeypatch):
    """Backoff never exceeds MAX_BACKOFF no matter how many failures occur."""
    sleeps = []
    client(Scripted(*[http_error(500)] * 10, ok(1)), sleeps).get("/p")
    assert max(sleeps) == fd.MAX_BACKOFF


def test_get_raises_permanent_on_4xx_and_error_status():
    """Client errors and `status: error` bodies are permanent and not retried."""
    with pytest.raises(fd.PermanentError):
        client(Scripted(http_error(400))).get("/p")
    err_body = Resp(json.dumps({"status": "error", "data": {"error": "nope"}}).encode())
    with pytest.raises(fd.PermanentError):
        client(Scripted(err_body)).get("/p")


# --------------------------------------------------------------------------- storage

def test_write_json_is_atomic(tmp_path):
    """write_json creates parent dirs and leaves no temp file behind."""
    p = tmp_path / "a" / "b.json"
    fd.write_json(p, {"k": 1})
    assert json.loads(p.read_text()) == {"k": 1}
    assert list(p.parent.iterdir()) == [p]


def test_store_failures_roundtrip(tmp_path):
    """Recorded permanent failures are read back as a set of keys."""
    s = fd.Store(tmp_path)
    assert s.failures() == set()
    s.record_failure("match:7:1", "gone")
    s.record_failure("list:7:u", "gone")
    assert s.failures() == {"match:7:1", "list:7:u"}


# ---------------------------------------------------------------------------- phases

def test_match_list_paginates_until_empty():
    """Pages backwards with `before` until an empty page; no fixed page cap."""
    api = FakeAPI({11: {"u": list(range(250, 0, -1))}})
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fd, "PAGE_SIZE", 100)
        matches = fd.fetch_match_list(client(api), "u", 11)
    assert [m["id"] for m in matches] == list(range(250, 0, -1))
    cursors = [re.search(r"before=(\d+)", u) for u in api.urls]
    assert [c and int(c[1]) for c in cursors] == [None, 151, 51, 1]


def test_match_list_stops_if_cursor_does_not_advance():
    """Guards against an API that ignores `before` and returns the same page forever."""
    page = ok([{"id": 5}])
    same = ok([{"id": 5}])
    assert fd.fetch_match_list(client(Scripted(page, same)), "u", 7) == [{"id": 5}]


def test_detail_order_is_deterministic_shuffle():
    """Order is a stable permutation (same across runs), different from sorted order."""
    ids = list(range(100))
    a, b = fd.detail_order(ids, 11), fd.detail_order(reversed(ids), 11)
    assert a == b and sorted(a) == ids and a != ids


def test_import_matches_links_and_skips_existing(tmp_path):
    """Existing match files are imported once; files already present are left alone."""
    src = tmp_path / "src"
    src.mkdir()
    for i in (1, 2):
        (src / f"{i}.json").write_text(json.dumps({"id": i}))
    s = fd.Store(tmp_path / "data")
    assert fd.import_matches(s, 7, src) == 2
    assert fd.import_matches(s, 7, src) == 0
    assert s.fetched_match_ids(7) == {1, 2}


def test_import_matches_falls_back_to_copy(tmp_path, monkeypatch):
    """If hard-linking fails (e.g. across filesystems), files are copied instead."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "3.json").write_text("{}")

    def no_link(*a):
        raise OSError("cross-device")

    monkeypatch.setattr(fd.os, "link", no_link)
    s = fd.Store(tmp_path / "data")
    assert fd.import_matches(s, 7, src) == 1
    assert s.match(7, 3).read_text() == "{}"


def test_run_fetches_everything_then_resumes_with_zero_requests(tmp_path):
    """A full run stores leaderboards, lists and details; a rerun makes no requests."""
    api = FakeAPI({11: {"a": [5, 4, 3], "b": [4, 2]}, 7: {"c": [9]}})
    s = fd.Store(tmp_path)
    fd.run(client(api), s, [11, 7])
    assert s.fetched_match_ids(11) == {2, 3, 4, 5}
    assert s.fetched_match_ids(7) == {9}
    assert json.loads(s.match_list(11, "a").read_text()) == [{"id": 5}, {"id": 4}, {"id": 3}]
    api.urls.clear()
    fd.run(client(api), s, [11, 7])
    assert api.urls == []


def test_run_resumes_after_partial_progress(tmp_path):
    """Already-fetched matches are skipped, only the missing ones are requested."""
    api = FakeAPI({11: {"a": [3, 2, 1]}})
    s = fd.Store(tmp_path)
    fd.fetch_match_lists(client(api), s, 11)
    fd.write_json(s.match(11, 2), {"id": 2})
    api.urls.clear()
    fd.fetch_match_details(client(api), s, 11)
    assert sorted(u.rsplit("/", 1)[1] for u in api.urls) == ["1", "3"]


def test_run_records_and_skips_permanent_failures(tmp_path):
    """Permanently failing matches/players are logged once and skipped on later runs."""
    api = FakeAPI({11: {"a": [2, 1], "bad": [7]}}, bad_matches={1}, bad_users={"bad"})
    s = fd.Store(tmp_path)
    fd.run(client(api), s, [11])
    assert s.failures() == {"match:11:1", "list:11:bad"}
    assert s.fetched_match_ids(11) == {2}
    api.urls.clear()
    fd.run(client(api), s, [11])
    assert api.urls == []


def test_status_reports_progress(tmp_path):
    """Status summarizes lists, details, failures and remaining time per season."""
    api = FakeAPI({11: {"a": [2, 1]}}, bad_matches={1})
    s = fd.Store(tmp_path)
    fd.fetch_match_lists(client(api), s, 11)
    out = fd.status(s)
    assert "season 11: lists 1/1, details 0/2 (0.0%), failed 0" in out
    fd.fetch_match_details(client(api), s, 11)
    out = fd.status(s)
    assert "details 1/2 (50.0%), failed 1" in out
    assert "remaining details: 0 (~0.0 h)" in out
    assert "still being fetched" not in out


def test_status_flags_incomplete_lists(tmp_path):
    """Before all match lists are fetched, status warns that the remaining count will grow."""
    s = fd.Store(tmp_path)
    fd.write_json(s.leaderboard(11), {"users": [{"uuid": "a"}, {"uuid": "b"}]})
    fd.write_json(s.match_list(11, "a"), [{"id": 1}])
    assert "still being fetched" in fd.status(s)


# ------------------------------------------------------------------------------- CLI

def test_main_run_and_status(tmp_path, capsys):
    """CLI `run` fetches into --data-dir and writes a log; `status` prints progress."""
    api = FakeAPI({11: {"a": [1]}})
    assert fd.main(["run", "--data-dir", str(tmp_path), "--seasons", "11"], client=client(api)) == 0
    assert (tmp_path / "fetch.log").exists()
    assert fd.main(["status", "--data-dir", str(tmp_path)]) == 0
    assert "details 1/1 (100.0%)" in capsys.readouterr().out


def test_main_import_option(tmp_path):
    """--import-matches SEASON=DIR reuses local files, avoiding detail requests."""
    src = tmp_path / "old"
    src.mkdir()
    (src / "1.json").write_text("{}")
    api = FakeAPI({7: {"a": [1]}})
    fd.main(["run", "--data-dir", str(tmp_path / "d"), "--seasons", "7", "--import-matches", f"7={src}"],
            client=client(api))
    assert not any("/matches/1" in u for u in api.urls)


def test_parse_import_rejects_bad_values():
    """--import-matches requires SEASON=DIR."""
    assert fd.parse_import("7=/x") == (7, Path("/x"))
    for bad in ("x=/y", "7", "7="):
        with pytest.raises(Exception):
            fd.parse_import(bad)


def test_lock_prevents_concurrent_runs(tmp_path, capsys):
    """A second fetcher on the same data dir exits instead of racing the first."""
    held = fd.acquire_lock(tmp_path)
    assert fd.acquire_lock(tmp_path) is None
    assert fd.main(["run", "--data-dir", str(tmp_path)], client=client(Scripted())) == 1
    assert "already running" in capsys.readouterr().err
    held.close()


def test_main_handles_interrupt(tmp_path, monkeypatch):
    """Ctrl-C exits with 130 and releases the lock so the next run can resume."""
    def boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(fd, "run", boom)
    assert fd.main(["run", "--data-dir", str(tmp_path)], client=client(Scripted())) == 130
    assert fd.acquire_lock(tmp_path) is not None
