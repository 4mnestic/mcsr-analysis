#!/usr/bin/env python3
"""Download MCSR Ranked data for seasons 7 and 11 into ~/mcsr-data.

Run:    python3 fetch_data.py      (no arguments; rerun any time to resume)
Check:  ls ~/mcsr-data/season-11/matches | wc -l

Assumptions:
- Public API, no key: 500 requests per 10 minutes, so it waits 1.2 s per request.
- Top 150 leaderboard players; ranked matches only, decay matches excluded.
- Season 7 matches already in ~/mcsr-analysis-season-7-data/matches are hard-linked
  instead of downloaded again.
- Matches the API can't find are saved as `null` so they are skipped next time.

Output: ~/mcsr-data/season-N/leaderboard.json
        ~/mcsr-data/season-N/match-lists/<player uuid>.json
        ~/mcsr-data/season-N/matches/<match id>.json
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.mcsrranked.com"
OUT = Path.home() / "mcsr-data"
OLD_SEASON_7 = Path.home() / "mcsr-analysis-season-7-data" / "matches"
SEASONS = (7, 11)


def get(path):
    """Return the API's `data` for path. Waits and retries on errors; None if not found."""
    while True:
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "mcsr-analysis"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                time.sleep(1.2)
                return json.load(resp)["data"]
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            print(f"HTTP {e.code} on {path}, retrying in 60 s", flush=True)
        except (OSError, ValueError) as e:
            print(f"{e!r} on {path}, retrying in 60 s", flush=True)
        time.sleep(60)


def save(path, data):
    """Write JSON via a temp file, so an interrupted run never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def match_list(uuid, season):
    """All of a player's ranked matches in a season, paging backwards 100 at a time."""
    matches, before = [], ""
    while page := get(f"/users/{uuid}/matches?season={season}&count=100&type=2&excludedecay=true{before}"):
        matches += page
        before = f"&before={page[-1]['id']}"
    return matches


for season in SEASONS:
    folder = OUT / f"season-{season}"
    if not (folder / "leaderboard.json").exists():
        save(folder / "leaderboard.json", get(f"/leaderboard?season={season}"))
    players = json.loads((folder / "leaderboard.json").read_text())["users"]
    for i, player in enumerate(players, 1):
        path = folder / "match-lists" / f"{player['uuid']}.json"
        if not path.exists():
            save(path, match_list(player["uuid"], season))
            print(f"season {season}: match list {i}/{len(players)} ({player['nickname']})", flush=True)

for season in SEASONS:
    folder = OUT / f"season-{season}"
    ids = sorted({m["id"] for f in (folder / "match-lists").glob("*.json") for m in json.loads(f.read_text())})
    for i, match_id in enumerate(ids, 1):
        path = folder / "matches" / f"{match_id}.json"
        old = OLD_SEASON_7 / f"{match_id}.json"
        if path.exists():
            continue
        if season == 7 and old.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            os.link(old, path)
            continue
        save(path, get(f"/matches/{match_id}"))
        if i % 100 == 0:
            print(f"season {season}: match {i}/{len(ids)}", flush=True)

print("Done. Data is in", OUT)
