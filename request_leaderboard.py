import json
import argparse
from myrequest import *

def get_leaderboard(season):
    request = ENDPOINT + f"/leaderboard?season={season}"
    response = send_get_request(request)
    posts = response.json()
    write_to_json(leaderboard_fname(season=season), posts)
    
    clean_data = [{
        "nickname": user['nickname'],
        "rank": user['seasonResult']['eloRank'],
        "elo": user['seasonResult']['eloRate'],
        "uuid": user['uuid']
    } for user in posts['data']['users']]

    write_to_json(leaderboard_clean_fname(season=season), clean_data)

if __name__ == "__main__":
    # Fetch and save season leaderboard data (as-is and cleaned and flattened)

    parser = argparse.ArgumentParser(description="Fetch the leaderboard for a given season.")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()
    get_leaderboard(season=args.season)
    