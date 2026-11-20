-- Does the rating system's predicted win probability match what actually happens?
--
-- The system's own prediction is recoverable from rating changes: every rated match
-- moves 40 points, so a winner gains 40 * (1 - p) and a loser loses 40 * p.
-- The 40 isn't documented; it's measured: the winner's gain always equals the loser's
-- loss, evenly rated players trade exactly 20, and at any rating gap a favorite's
-- gain-if-win plus loss-if-lose is 40.

-- One row per rated match, seen from the favorite (higher pre-match rating).
create view favorites as
select
    m.season,
    m.match_id,
    m.outcome,
    f.won::int as won,
    f.won::int - f.elo_change / 40 as predicted,
    (f.elo_before + u.elo_before) / 2 as match_elo
from matches m
join match_players f on f.match_id = m.match_id
join match_players u on u.match_id = m.match_id and u.uuid <> f.uuid
where f.elo_before > u.elo_before;  -- drops unrated matches and exact ties

-- Predicted vs. actual favorite win rate, in 5-point bins of predicted probability.
create view calibration as
select
    season,
    floor(predicted * 20) / 20 as bin,
    count(*) as matches,
    avg(predicted) as predicted,
    avg(won) as actual,
    ci95(avg(won), count(*)) as ci
from favorites
where outcome <> 'no result'
group by all;
