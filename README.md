# mcsr-analysis

Independent analysis of MCSR Ranked data (public [MCSR Ranked API](https://docs.mcsrranked.com)).

## Fetching data

```sh
tmux new -s fetch 'python3 fetch_data.py'   # rerun the same command to resume
```

Downloads seasons 7 and 11 into `~/mcsr-data`. Assumptions are listed at the top of
[`fetch_data.py`](fetch_data.py).
