import os
import argparse
from request_match_list import get_match_list
from myrequest import *

if __name__ == "__main__":
    # Fetch match lists for the top 150 players for a given season.
    # https://docs.mcsrranked.com/#leaderboard
    parser = argparse.ArgumentParser(description="Fetch match lists for the top 150 players for a given season.")
    parser.add_argument("--season", default="7", help="Season number (default: 7)")
    
    args = parser.parse_args()
    
    leaderboard = read_json(leaderboard_clean_fname(season=args.season))
    for user in leaderboard:
        nickname = user['nickname']
        if os.path.exists(match_list_fname(nickname=nickname, season=args.season)):
            print(f"Skipping {nickname}: their match list already exists for season {args.season}")
        else:
            print(f'Getting matches for {nickname} (season {args.season})...')
            get_match_list(nickname, season=args.season)