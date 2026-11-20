#!/usr/bin/env python3
"""Download MCSR Ranked match data for seasons 7 and 11 into ~/mcsr-data.

Run:    python3 fetch_data.py            (no arguments; rerun any time to resume)
Check:  python3 fetch_data.py --status

Assumptions:
- Public API, no key: 500 requests per 10 minutes, so it waits 1.2 s per request.
- Top 150 leaderboard players; ranked matches only, decay matches excluded.
- Takes about an hour per season.

Output: ~/mcsr-data/season-N/leaderboard.json
        ~/mcsr-data/season-N/match-lists/<player uuid>.json
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.mcsrranked.com"
OUT = Path.home() / "mcsr-data"
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


if sys.argv[1:] == ["--status"]:
    for season in SEASONS:
        lists = len(list((OUT / f"season-{season}" / "match-lists").glob("*.json")))
        print(f"season {season}: match lists {lists}/150")
    sys.exit()

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

print("Done. Data is in", OUT)
