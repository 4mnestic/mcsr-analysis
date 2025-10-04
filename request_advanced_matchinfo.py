import json
import sys
import argparse

from myrequest import *
 
def get_advanced_match_info(match_id, season):
    # Given a match_id, query the /matches endpoint for advanced MatchInfo

    request = ENDPOINT + f"/matches/{match_id}"
    response = send_get_request(request)
    if not response:
        return None

    data = response.json()['data']

    outfile_name = matchinfo_advanced_fname(match_id)
    write_to_json(outfile_name, data)
    print(f"Advanced MatchInfo (id={match_id}) written to {outfile_name}", file=sys.stderr)

if __name__ == "__main__":
    # Fetch advanced MatchInfo for a given match_id.
    parser = argparse.ArgumentParser(description="Fetch advanced MatchInfo for a given match_id.")
    parser.add_argument("match_id", help="https://docs.mcsrranked.com/#matches-matchid", required=True)
    parser.add_argument("--season", default="7", help="Season number (default: 7)")
    args = parser.parse_args()
    
    get_advanced_match_info(args.match_id, args.season)