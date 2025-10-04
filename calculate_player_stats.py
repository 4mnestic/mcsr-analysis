import argparse

from myrequest import *

# assuming I have the data cleaned to my liking

def calc_means(player, season=7):
    # calculate the average completion time for matches that player won
    match_list = read_json(match_list_fname(player))

    ### Stats to track
    completions = []
    nether_enters = []
    nether_to_forts = []
    end_to_completion = []
    total_games = 0
    total_forfeits = 0

    for match_id in match_list:
        match_info = read_json(matchinfo_advanced_cleaned_fname(match_id, season=season))
        write_to_json("buffer.json", match_info)
        player_uuid = match_info['player1uuid'] if match_info['player1'] == player else match_info['player2uuid']

        ### Updating stats
        total_games += 1
        if match_info['winner'] == player_uuid:
            completions.append(match_info['final_time'])
            try:
                end_to_completion.append(match_info['final_time'] - match_info['advancements']['story.enter_the_end'][player_uuid])
            except KeyError:
                pass
        try:
            nether_enters.append(match_info['advancements']['story.enter_the_nether'][player_uuid])
        except KeyError:
            pass
        try:
            nether_to_forts.append(match_info['advancements']['nether.find_fortress'][player_uuid] - match_info['advancements']['story.enter_the_nether'][player_uuid])
        except KeyError:
            pass
        if match_info['winner'] != player_uuid and match_info['forfeited'] == True:
            total_forfeits += 1
        
        
    avg = lambda x: sum(x)/len(x)/60000
    stats = {
        "average_time_to_completion": avg(completions),
        "average_time_to_nether_enter": avg(nether_enters),
        "average_time_from_nether_to_fort": avg(nether_to_forts),
        "average_time_from_end_to_completion": avg(end_to_completion),
        "forfeit_rate": total_forfeits / total_games
    }
    outfile_name = player_stats_fname(player, season=season)
    write_to_json(outfile_name, stats)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Calculate statistics for a given player from cleaned matchinfo files.")
    parser.add_argument("user_id", help="https://docs.mcsrranked.com/#users-identifier-matches")
    parser.add_argument("--season", default=SEASON, help="Season number (default: 7)")
    args = parser.parse_args()

    calc_means(args.user_id, season=args.season)