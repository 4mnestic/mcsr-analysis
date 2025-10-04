import json
import sys
import csv
import os
import argparse
from myrequest import *

def clean_match(match_id, season=7):
    match_info = read_json(matchinfo_advanced_fname(match_id, season=season))

    del match_info['type']
    del match_info['category']
    del match_info['gameMode']
    del match_info['spectators']
    del match_info['changes']
    del match_info['completions']
    del match_info['tag']
    del match_info['replayExist']
    del match_info['bastionType']
    del match_info['seedType']
    del match_info['decayed']
    del match_info['rank']

    match_info["overworld"] = match_info["seed"].pop("overworld")
    match_info["nether"] = match_info["seed"].pop("nether")
    match_info["endTowers"] = match_info["seed"].pop("endTowers")
    del match_info['seed']

    match_info["player1"] = match_info['players'][0]['nickname']
    match_info["player1uuid"] = match_info['players'][0]['uuid']
    match_info["player2"] = match_info['players'][1]['nickname']
    match_info["player2uuid"] = match_info['players'][1]['uuid']
    del match_info['players']

    match_info['winner'] = match_info['result']['uuid']
    match_info['final_time'] = match_info['result']['time']
    del match_info['result']

    player1uuid = match_info['player1uuid']
    player2uuid = match_info['player2uuid']
    match_info['advancements'] = dict()
    for advancement in match_info['timelines']:
        if not advancement['type'] in match_info['advancements']:
            match_info['advancements'][advancement['type']] = dict()
        match_info['advancements'][advancement['type']][advancement['uuid']] = advancement['time']
    del match_info['timelines']

    outfile_name = matchinfo_advanced_cleaned_fname(match_id, season=season)
    write_to_json(outfile_name, match_info)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Clean matchinfo for a given matchid (default season 7).")
    parser.add_argument("match_id", help="https://docs.mcsrranked.com/#matches-matchid")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()

    outfile_name = matchinfo_advanced_cleaned_fname(args.match_id, season=args.season)
    if os.path.exists(outfile_name):
        print(f"Skipping file (already exists): {outfile_name}")
    else:
        clean_match(args.match_id, season=args.season)