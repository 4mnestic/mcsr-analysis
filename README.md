# mcsr-analysis

Independent analysis of MCSR Ranked data (public [MCSR Ranked API](https://docs.mcsrranked.com)).

## Fetching data

`fetch_data.py` downloads, for Seasons 11 and 7: the top-150 leaderboard, every ranked
match summary for those players, and full match details (timelines). Standard library
only; no API key needed.

```sh
# start (or resume) in a detachable session; reuses the already-downloaded Season 7 matches
tmux new -s fetch 'python3 fetch_data.py run --import-matches 7=~/mcsr-analysis-season-7-data/matches'

python3 fetch_data.py status   # progress + time estimate
tail -f ~/mcsr-data/fetch.log  # live log
```

- **Rate limits:** respects the API's `ratelimit` header (500 requests / 10 min ≈ 3,000/h)
  and 429s; retries network and server errors forever with backoff.
- **Resumable:** files are written atomically; kill it any time (Ctrl-C, reboot) and rerun
  the same command. A lock file prevents two fetchers running at once.
- **Order:** leaderboards → match lists (minutes) → match details (hours), smallest
  backlog first. Details are fetched in a fixed shuffled order, so a partial season is a
  random sample.
- **Permanent failures** (e.g. a match the API no longer has) go to `failed.jsonl` and
  are skipped on reruns; delete that file to retry them.

Data lands in `~/mcsr-data` (override with `--data-dir` or `$MCSR_DATA_DIR`):

```
~/mcsr-data/
  season-11/leaderboard.json          leaderboard (API `data` payload)
  season-11/match-lists/<uuid>.json   all match summaries for one player
  season-11/matches/<id>.json         full match details, incl. timelines
  season-7/...
  failed.jsonl  fetch.log
```

## Tests

```sh
pip install pytest pytest-cov
pytest --cov=fetch_data tests
```
