import requests
import json
import os
import datetime
import sys

### CONSTANTS
keyfile = open("secrets/api_key", 'r')
API_KEY = keyfile.read() 
keyfile.close()

ENDPOINT = 'https://api.mcsrranked.com'
COUNT = 100
SEASON = 7

# Funtions used by mant scripts

def human_readable_date(epoch_time):
    return datetime.datetime.utcfromtimestamp(epoch_time).strftime("%Y-%m-%d %H:%M:%S")

def human_readable_time(ms):
    return ms / 1000 / 60

def match_list_fname(nickname, season=7):
    return f'season-{season}/players/{nickname}/{nickname}-match-ids.json'

def leaderboard_fname(season=7):
    return f'season-{season}/leaderboard.json'

def leaderboard_clean_fname(season=7):
    return f'season-{season}/leaderboard-cleaned.json'

def matchinfo_advanced_fname(match_id, season=7):
    return f'season-{season}/matches/{match_id}.json'

def matchinfo_advanced_cleaned_fname(match_id, season=7):
    return f'season-{season}/matches-cleaned/{match_id}-cleaned.json'

def send_get_request(query_string):
    # Helper method for main methods to reduce boilerpate
    try:
        response = requests.get(query_string, headers={"API-Key": f"{API_KEY}"})
        response.raise_for_status()  # Raises HTTPError for bad status
        return response
    except requests.exceptions.RequestException as e:
        print('Request failed:', e, file=sys.stderr)
        return None


def read_json(fname):
    try:
        matches = json.load(open(fname, 'r'))
        return matches
    except json.JSONDecodeError as e:
        print("Decoding failed: ", e, file=sys.stderr)
        return None
    except FileNotFoundError as e:
        print("File not found: ", {fname}, file=sys.stderr)
    
def write_to_json(outfile_name, python_object):
    # takes a python object and writes to josn file

    if "/" in outfile_name:
        os.makedirs(os.path.dirname(outfile_name), exist_ok=True)

    outfile = open(outfile_name, "w")
    print(json.dumps(python_object), file=outfile)


def player_stats_fname(nickname, season=7):
    return f'season-{season}/players/{nickname}/{nickname}-stats.json'