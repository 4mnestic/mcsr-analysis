import json
import sys
import csv
import os
import argparse
from myrequest import *
from calculate_player_stats import calc_means

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Clean matchinfo for all matches played by the top players (on leaderboard) (default season 7).")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()

    players = [player["nickname"] for player in read_json(leaderboard_clean_fname(season=args.season))]
    for player in players:
        # calc_means(player, season=args.season)
        print(f"Calculating player stats: {player}", file=sys.stderr)
    

    player_stats = [read_json(player_stats_fname(player)) for player in players]

    with open("output.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=player_stats[0].keys())
        writer.writeheader()
        writer.writerows(player_stats)
    
