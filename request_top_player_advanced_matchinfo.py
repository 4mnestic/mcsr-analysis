import os
import argparse
from request_match_list import get_match_list
from request_advanced_matchinfo import get_advanced_match_info
from request_leaderboard import get_leaderboard
from myrequest import *

def get_top_players_advanced_matchinfo(season):
    # Fetch advanced MatchInfo for top 150 players in a given season (default season 7).
    # Saved under /season-{season}/matches/
    # Thus far, I have fully fetched all matches for all top 150 runners in season 7
    # https://docs.mcsrranked.com/#leaderboard

    if not os.path.exists(leaderboard_clean_fname(season=args.season)):
        get_leaderboard(season=season)
    leaderboard = read_json(leaderboard_clean_fname(season=args.season))

    for user in leaderboard:
        nickname = user['nickname']
        print(f'Getting advanced MatchInfo for {nickname} (season {args.season})...')
        if not os.path.exists(match_list_fname(nickname=nickname, season=args.season)):
            get_match_list(user_id=nickname, season=season)
        user_matches = read_json(match_list_fname(nickname=nickname, season=args.season))
        for match_id in user_matches:
            if os.path.exists(matchinfo_advanced_fname(match_id=match_id, season=args.season)):
                print(f"Skipping match (id={match_id}): MatchInfo file already exists for season {args.season}.")
            else:
                get_advanced_match_info(match_id=match_id, season=args.season)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch advanced MatchInfo for top 150 players in a given season (default season 7).")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()
    get_top_players_advanced_matchinfo(season=args.season)