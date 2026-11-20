#!/usr/bin/env python3
"""Resumable, rate-limit-aware fetcher for MCSR Ranked API data.

For each season it fetches:
  1. the leaderboard (top 150 players),
  2. every ranked match summary for each leaderboard player (no page cap),
  3. full match details (with timelines) for every match in those lists.

No API key needed (unauthenticated limit: 500 requests / 10 min). Every file is
written atomically, so the process can be killed at any time; rerunning skips
everything already on disk. Match details are fetched in a fixed shuffled order,
so a partially finished season is an unbiased random sample.

Usage:
    python3 fetch_data.py run    [--data-dir DIR] [--seasons 11 7] [--import-matches 7=DIR]
    python3 fetch_data.py status [--data-dir DIR]
"""
from __future__ import annotations

import argparse
import fcntl
import http.client
import json
import logging
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.mcsrranked.com"
DEFAULT_DATA_DIR = Path(os.environ.get("MCSR_DATA_DIR", Path.home() / "mcsr-data"))
DEFAULT_SEASONS = [11, 7]
PAGE_SIZE = 100
SHUFFLE_SEED = 20261120
REQUESTS_PER_HOUR = 3000  # 500 per 10 minutes
USER_AGENT = "mcsr-analysis-fetcher/1.0"
MAX_BACKOFF = 600
PROGRESS_EVERY = 250

log = logging.getLogger("fetch_data")


class PermanentError(Exception):
    """A request failed in a way retrying won't fix (e.g. unknown match id)."""


# --------------------------------------------------------------------------- HTTP

def parse_ratelimit(headers) -> tuple[int, int] | None:
    """Return (remaining, seconds_until_reset) from the `ratelimit` header, if present."""
    m = re.search(r"r=(\d+).*?t=(\d+)", headers.get("ratelimit", "") or "")
    return (int(m[1]), int(m[2])) if m else None


def retry_after(headers) -> int:
    """Seconds to wait after a 429: Retry-After, else the rate-limit reset, else 60."""
    value = headers.get("Retry-After") if headers else None
    if value and str(value).isdigit():
        return int(value)
    rl = parse_ratelimit(headers) if headers else None
    return rl[1] + 1 if rl else 60


class Client:
    """Minimal API client: retries transient failures forever and waits out rate limits."""

    def __init__(self, opener=urllib.request.urlopen, sleep=time.sleep):
        self.opener = opener
        self.sleep = sleep
        self.requests = 0

    def get(self, path: str):
        backoff = 5
        while True:
            req = urllib.request.Request(API + path, headers={"User-Agent": USER_AGENT})
            try:
                with self.opener(req, timeout=60) as resp:
                    body, headers = resp.read(), resp.headers
                self.requests += 1
                payload = json.loads(body)
                self._throttle(headers)
                if payload.get("status") != "success":
                    raise PermanentError(f"{path}: {payload.get('data')}")
                return payload["data"]
            except urllib.error.HTTPError as e:
                self.requests += 1
                if e.code == 429:
                    wait = retry_after(e.headers)
                    log.warning("rate limited on %s; sleeping %ss", path, wait)
                    self.sleep(wait)
                    continue
                if 400 <= e.code < 500:
                    raise PermanentError(f"{path}: HTTP {e.code}") from e
                err = f"HTTP {e.code}"
            except (OSError, http.client.HTTPException, json.JSONDecodeError) as e:
                err = repr(e)
            log.warning("%s on %s; retrying in %ss", err, path, backoff)
            self.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    def _throttle(self, headers):
        rl = parse_ratelimit(headers)
        if rl and rl[0] <= 1:
            log.info("rate limit window exhausted; sleeping %ss", rl[1] + 1)
            self.sleep(rl[1] + 1)


# ------------------------------------------------------------------------ Storage

def write_json(path: Path, obj) -> None:
    """Write JSON atomically (temp file + rename) so interrupted writes never leave partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)


class Store:
    """On-disk layout:

    <root>/season-<N>/leaderboard.json          leaderboard API `data`
    <root>/season-<N>/match-lists/<uuid>.json   all match summaries for one player
    <root>/season-<N>/matches/<id>.json         full match details (timelines)
    <root>/failed.jsonl                          permanent failures (skipped on rerun)
    <root>/fetch.log                             run log
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    def season_dir(self, season) -> Path:
        return self.root / f"season-{season}"

    def leaderboard(self, season) -> Path:
        return self.season_dir(season) / "leaderboard.json"

    def match_list(self, season, uuid) -> Path:
        return self.season_dir(season) / "match-lists" / f"{uuid}.json"

    def match(self, season, match_id) -> Path:
        return self.season_dir(season) / "matches" / f"{match_id}.json"

    @property
    def failed_path(self) -> Path:
        return self.root / "failed.jsonl"

    def failures(self) -> set[str]:
        if not self.failed_path.exists():
            return set()
        return {json.loads(line)["key"] for line in self.failed_path.read_text().splitlines() if line}

    def record_failure(self, key: str, reason: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.failed_path.open("a") as f:
            f.write(json.dumps({"key": key, "reason": reason, "at": int(time.time())}) + "\n")

    def seasons_on_disk(self) -> list[int]:
        return sorted(int(p.name.split("-")[1]) for p in self.root.glob("season-*") if p.is_dir())

    def match_ids(self, season) -> list[int]:
        """All match ids referenced by this season's completed match lists."""
        ids = set()
        for f in (self.season_dir(season) / "match-lists").glob("*.json"):
            ids.update(m["id"] for m in json.loads(f.read_text()))
        return sorted(ids)

    def fetched_match_ids(self, season) -> set[int]:
        return {int(p.stem) for p in (self.season_dir(season) / "matches").glob("*.json")}


# ------------------------------------------------------------------------- Phases

def fetch_leaderboard(client: Client, store: Store, season) -> list[dict]:
    path = store.leaderboard(season)
    if not path.exists():
        write_json(path, client.get(f"/leaderboard?season={season}"))
        log.info("season %s: leaderboard saved", season)
    return json.loads(path.read_text())["users"]


def fetch_match_list(client: Client, uuid: str, season) -> list[dict]:
    """Page backwards through a player's ranked (non-decay) matches until exhausted."""
    matches, before = [], None
    while True:
        q = f"/users/{uuid}/matches?season={season}&count={PAGE_SIZE}&type=2&excludedecay=true"
        if before is not None:
            q += f"&before={before}"
        page = client.get(q)
        if not page or page[-1]["id"] == before:
            return matches
        matches.extend(page)
        before = page[-1]["id"]


def fetch_match_lists(client: Client, store: Store, season) -> None:
    users = fetch_leaderboard(client, store, season)
    failed = store.failures()
    todo = [u for u in users
            if not store.match_list(season, u["uuid"]).exists() and f"list:{season}:{u['uuid']}" not in failed]
    log.info("season %s: %d/%d match lists remaining", season, len(todo), len(users))
    for i, u in enumerate(todo, 1):
        try:
            matches = fetch_match_list(client, u["uuid"], season)
        except PermanentError as e:
            store.record_failure(f"list:{season}:{u['uuid']}", str(e))
            log.error("season %s: match list for %s failed permanently: %s", season, u["nickname"], e)
            continue
        write_json(store.match_list(season, u["uuid"]), matches)
        log.info("season %s: [%d/%d] %s: %d matches", season, i, len(todo), u["nickname"], len(matches))


def detail_order(ids, season) -> list[int]:
    """Deterministic shuffle: identical across restarts, so partial progress is a random sample."""
    ordered = sorted(ids)
    random.Random(SHUFFLE_SEED + int(season)).shuffle(ordered)
    return ordered


def remaining_details(store: Store, season) -> list[int]:
    have, failed = store.fetched_match_ids(season), store.failures()
    return [i for i in detail_order(store.match_ids(season), season)
            if i not in have and f"match:{season}:{i}" not in failed]


def fetch_match_details(client: Client, store: Store, season) -> None:
    todo = remaining_details(store, season)
    log.info("season %s: %d match details remaining (~%.1f h)", season, len(todo), len(todo) / REQUESTS_PER_HOUR)
    for i, mid in enumerate(todo, 1):
        try:
            write_json(store.match(season, mid), client.get(f"/matches/{mid}"))
        except PermanentError as e:
            store.record_failure(f"match:{season}:{mid}", str(e))
            log.error("season %s: match %s failed permanently: %s", season, mid, e)
        if i % PROGRESS_EVERY == 0 or i == len(todo):
            left = len(todo) - i
            log.info("season %s: details %d/%d this run (%d left, ~%.1f h)",
                     season, i, len(todo), left, left / REQUESTS_PER_HOUR)


def import_matches(store: Store, season, src: Path) -> int:
    """Hard-link (or copy) previously downloaded match files so they aren't re-fetched."""
    n = 0
    for f in Path(src).expanduser().glob("*.json"):
        dst = store.match(season, f.stem)
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(f, dst)
        except OSError:
            shutil.copy2(f, dst)
        n += 1
    log.info("season %s: imported %d existing match files from %s", season, n, src)
    return n


def run(client: Client, store: Store, seasons, imports=()) -> None:
    for season, src in imports:
        import_matches(store, season, src)
    for season in seasons:  # cheap: a few thousand requests total
        fetch_match_lists(client, store, season)
    # Finish the smallest backlog first so nearly-complete seasons complete.
    for season in sorted(seasons, key=lambda s: len(remaining_details(store, s))):
        fetch_match_details(client, store, season)
    log.info("all done (%d requests this run). Data in %s", client.requests, store.root)


# ------------------------------------------------------------------------- Status

def status(store: Store) -> str:
    lines = [f"data dir: {store.root}"]
    failures = store.failures()
    total_left, lists_pending = 0, False
    for season in store.seasons_on_disk():
        lb = store.leaderboard(season)
        n_players = len(json.loads(lb.read_text())["users"]) if lb.exists() else 0
        n_lists = len(list((store.season_dir(season) / "match-lists").glob("*.json")))
        ids = store.match_ids(season)
        have = store.fetched_match_ids(season) & set(ids)
        n_failed = sum(1 for k in failures if k.startswith((f"match:{season}:", f"list:{season}:")))
        left = len(ids) - len(have) - sum(1 for k in failures if k.startswith(f"match:{season}:"))
        total_left += left
        lists_pending |= n_lists + n_failed_lists(failures, season) < n_players or not lb.exists()
        pct = 100 * len(have) / len(ids) if ids else 0
        lines.append(f"season {season}: lists {n_lists}/{n_players}, "
                     f"details {len(have)}/{len(ids)} ({pct:.1f}%), failed {n_failed}")
    note = " so far; match lists still being fetched, so this will grow" if lists_pending else ""
    lines.append(f"remaining details: {total_left} (~{total_left / REQUESTS_PER_HOUR:.1f} h){note}")
    return "\n".join(lines)


def n_failed_lists(failures: set[str], season) -> int:
    return sum(1 for k in failures if k.startswith(f"list:{season}:"))


# ---------------------------------------------------------------------------- CLI

def acquire_lock(root: Path):
    """Hold an exclusive lock so two fetchers never run against the same data dir."""
    root.mkdir(parents=True, exist_ok=True)
    fh = (root / ".lock").open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    return fh


def parse_import(value: str) -> tuple[int, Path]:
    season, _, path = value.partition("=")
    if not season.isdigit() or not path:
        raise argparse.ArgumentTypeError("expected SEASON=DIR, e.g. 7=~/mcsr-analysis-season-7-data/matches")
    return int(season), Path(path).expanduser()


def setup_logging(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.handlers.clear()
    for h in (logging.StreamHandler(), logging.FileHandler(root / "fetch.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def main(argv=None, client: Client | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["run", "status"])
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                   help=f"where data is stored (default: {DEFAULT_DATA_DIR}, or $MCSR_DATA_DIR)")
    p.add_argument("--seasons", type=int, nargs="+", default=DEFAULT_SEASONS)
    p.add_argument("--import-matches", type=parse_import, action="append", default=[],
                   metavar="SEASON=DIR", help="reuse already-downloaded match files")
    args = p.parse_args(argv)
    root = args.data_dir.expanduser()

    if args.command == "status":
        print(status(Store(root)))
        return 0

    lock = acquire_lock(root)
    if lock is None:
        print(f"another fetcher is already running on {root}", file=sys.stderr)
        return 1
    setup_logging(root)
    log.info("starting: seasons=%s data dir=%s", args.seasons, root)
    try:
        run(client or Client(), Store(root), args.seasons, args.import_matches)
    except KeyboardInterrupt:
        log.info("interrupted; rerun the same command to resume")
        return 130
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
