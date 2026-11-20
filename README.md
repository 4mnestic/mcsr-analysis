# MCSR Ranked: an independent analysis

[MCSR Ranked](https://mcsrranked.com) is a 1v1 ladder for Minecraft speedrunning: two players race to beat the game on the same randomly chosen seed. Using the public API, this looks at 56,454 ranked matches from Season 7 (Dec 2024 – Apr 2025) involving the top 150 players.

## Findings

### 1. The rating system's win predictions are accurate

![Predicted vs. actual favorite win rate](figures/calibration.png)

The system's predicted win probability can be recovered from rating changes: every match moves 40 points, so a winner gains 40 × (1 − p). Across all matches, predicted and actual win rates differ by 0.4 percentage points on average. The only gap is above 75% predicted (2% of matches), where favorites win about 4 points less often than predicted.

**Implication:** predictions are reliable enough to show players or to use in matchmaking as they are.

### 2. Lopsided matches are abandoned more often, but only within a skill level

![Abandonment rate, close vs. lopsided matches](figures/abandonment.png)

A match is *close* if the favorite's predicted win probability is under 60%, and *abandoned* if it ended in a forfeit or with no result. Overall, close and lopsided matches look the same (33% vs. 34% abandoned). Within each skill level, lopsided matches are abandoned more: 44% vs. 52% below 1500 Elo, 28% vs. 34% at 1500–1800. The aggregate hides this because skill level drives abandonment far more than closeness: 44–52% below 1500, about 20% above 1800.

**Implication:** tighter matchmaking for lower-rated players may reduce abandonment. This is observational, so it's a hypothesis for an experiment, not a result.

### 3. The seed pool is balanced

![Median completion time by seed type](figures/seed_completion_time.png)

Seeds are assigned at random, so differences between seed types are effects of the seed. Seed type shifts median completion time by at most 0.7 minutes (ruined portal 10.7, village 11.4) and completion rate by at most 4 points (65–69%). On every seed type, favorites win as often as predicted (within 1 point), so no seed type swaps skill for luck.

**Implication:** no seed type needs removing.

## Data and limitations

- Every match involves at least one top-150 player, so results describe high-level play, not the whole ladder.
- Only matches with a rated favorite are used for findings 1 and 2 (ties and unrated matches excluded).
- Data from the [MCSR Ranked API](https://docs.mcsrranked.com).

## Reproduce

```sh
python3 fetch_data.py                 # download raw data to ~/mcsr-data (hours; resumable)
pip install -r requirements.txt
python3 analysis.py                   # build tables, print results, save figures/
```

`sql/` holds the table build and each analysis; `test_build.py` checks the table build.
