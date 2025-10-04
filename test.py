from myrequest import *


leaderboard = read_json(leaderboard_clean_fname(season=7))

player_names = {player['nickname'] for player in leaderboard}

for name in player_names:
    match_list = read_json(match_list_fname(name, season=7))
    num_matches = 0
    num_decay_matches = 0
    for match_id in match_list:
        match_info = read_json(matchinfo_advanced_fname(match_id))
        num_matches+=1
        if match_info['decayed'] == True:
            num_decay_matches += 1

    avg = num_decay_matches /num_matches

    print(name, avg)

    # Findings: Lots of players have not-1.0 proportions of filtered seeds.
    # All matches are ranked matches
    # 