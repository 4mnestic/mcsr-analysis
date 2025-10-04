import json
import sys
import argparse

from myrequest import *

def _match_request(user_id, season, before=None):
    # Helper method for get_matches. return a formatted query string for user matches

    user_matches_query = f"/users/{user_id}/matches"
    parameters = "&".join([
        f"season={season}", f"count={COUNT}", "excludedecay=true", "type=2"
    ])
    if before:
        parameters += f"&before={before}"
    request =  ENDPOINT + user_matches_query + "?" + parameters
    return request


def get_match_list(user_id, season=7):
    # This script pulls all of a given user's match IDs for a given season.
    # Using the "before" query parameter, we can retrieve
    # and compile a complete list of matches.

    # Saves a JSON formatted list of match IDs.

    # Begin the match list and keep track of the earliest match id added
    # with the `before` variable
    matches = []
    request = _match_request(user_id, season)
    response = send_get_request(request)
    if not response: # Exit if response fails
        return None
    
    try:
        posts = response.json()
        num_matches = len(posts['data'])
        print("# matches retrieved:", num_matches, file=sys.stderr)

        before = posts["data"][-1]["id"]
        matches.extend(match["id"] for match in posts["data"])

    except json.JSONDecodeError as e:
        print('JSON decoding failed:', e, file=sys.stderr)
        return None 
    
    for _ in range(10):
        request = _match_request(user_id, season, before)
        response = send_get_request(request)
        if not response:
            break
        try:
            posts = response.json()
            num_matches = len(posts["data"])
            print("# matches retrieved:", num_matches, file=sys.stderr)
            if num_matches == 0:
                break

            before = posts["data"][-1]["id"]
            matches.extend(match['id'] for match in posts["data"])
        except json.JSONDecodeError as e:
            print('JSON decoding failed:', e, file=sys.stderr)
            return None 
    
    outfile_name = match_list_fname(season=season, nickname=user_id)
    write_to_json(outfile_name, matches)
    print(f"Match list written to {outfile_name}", file=sys.stderr)


if __name__ == "__main__":
    # Fetch match list for a given player in a given season (default season 7).

    parser = argparse.ArgumentParser(description="Fetch match list for a given player in a given season (default season 7).")
    parser.add_argument("user_id", help="https://docs.mcsrranked.com/#users-identifier-matches", required=True)
    parser.add_argument("--season", default="7", help="Season number (default: 7)")
    args = parser.parse_args()
    
    get_match_list(args.user_id, args.season)