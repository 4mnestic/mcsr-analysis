import json

import duckdb


def match(id, winner, forfeited=False, time=600_000):
    return {
        "id": id, "season": 11, "date": 1_780_000_000, "forfeited": forfeited,
        "seed": {"overworld": "VILLAGE", "nether": "BRIDGE", "variations": []},
        "result": {"uuid": winner, "time": time},
        "players": [{"uuid": "a", "nickname": "A"}, {"uuid": "b", "nickname": "B"}],
        "changes": [{"uuid": "a", "eloRate": 1600, "change": 15 if winner == "a" else -25},
                    {"uuid": "b", "eloRate": 1500, "change": -15 if winner == "a" else 25}],
    }


def build(tmp_path, monkeypatch):
    lists = tmp_path / "mcsr-data" / "season-11" / "match-lists"
    lists.mkdir(parents=True)
    # Match 1 appears in both players' lists, as it does in the real data.
    (lists / "a.json").write_text(json.dumps([match(1, "a"), match(2, "b", forfeited=True)]))
    (lists / "b.json").write_text(json.dumps([match(1, "a"), match(3, None, forfeited=True)]))
    monkeypatch.setenv("HOME", str(tmp_path))
    con = duckdb.connect()
    for name in ["build", "elo_calibration"]:
        con.execute(open(f"sql/{name}.sql").read())
    return con


def test_matches_are_deduplicated_and_classified(tmp_path, monkeypatch):
    """Each match appears once, with the right outcome and a completion time only if completed."""
    con = build(tmp_path, monkeypatch)
    rows = con.sql("select match_id, outcome, completion_min from matches order by 1").fetchall()
    assert rows == [(1, "completed", 10.0), (2, "forfeit", None), (3, "no result", None)]
    assert con.sql("select count(*) from match_players").fetchone() == (6,)


def test_favorite_prediction_is_recovered_from_rating_change(tmp_path, monkeypatch):
    """The favorite's predicted win probability is won - change / 40, whether they won or lost."""
    con = build(tmp_path, monkeypatch)
    rows = con.sql("select match_id, won, predicted from favorites order by 1").fetchall()
    assert rows == [(1, 1, 0.625), (2, 0, 0.625), (3, None, None)]
