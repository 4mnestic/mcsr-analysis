import json
import sys
import csv
import os
import argparse
from myrequest import *
from clean_match import clean_match


def clean_player_matches(user_id, season=7):
    match_list = read_json(match_list_fname(user_id, season=season))

    for match_id in match_list:
        outfile_name = matchinfo_advanced_cleaned_fname(match_id, season=season)
        if os.path.exists(outfile_name):
            print(f"Skipping file (already exists): {outfile_name}")
        else:
            clean_match(match_id, season=season)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Clean matchinfo for all matches played by the supplied user (default season 7).")
    parser.add_argument("user_id", help="https://docs.mcsrranked.com/#users-identifier-matches")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()

    clean_player_matches(args.user_id, args.season)