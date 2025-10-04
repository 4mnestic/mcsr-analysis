import json
import sys
import csv
import os
import argparse
from myrequest import *
from clean_player_matches import clean_player_matches

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Clean matchinfo for all matches played by the top players (on leaderboard) (default season 7).")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()

    players = [player["nickname"] for player in read_json(leaderboard_clean_fname(season=args.season))]
    for player in players:
        clean_player_matches(player, season=args.season)