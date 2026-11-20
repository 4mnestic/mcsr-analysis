-- Is the seed pool balanced? Seeds are assigned at random, so differences between
-- seed types are effects of the seed, not of who happened to play it.

-- Per seed type: how often matches finish, how long they take, and whether the
-- favorite wins as often as the rating system predicts (i.e. skill still decides).
-- Uses the `favorites` view from elo_calibration.sql.
create view seed_balance as
with by_seed as (
    select 'overworld' as feature, overworld as seed_type, m.*, f.won, f.predicted
    from matches m left join favorites f using (match_id)
    union all
    select 'bastion', bastion, m.*, f.won, f.predicted
    from matches m left join favorites f using (match_id)
),
-- 95% interval for the median: the completion times ranked n/2 ± 0.98·√n.
ranked as (
    select
        season, feature, seed_type, completion_min,
        row_number() over (partition by season, feature, seed_type order by completion_min) as r,
        count(*) over (partition by season, feature, seed_type) as n
    from by_seed
    where completion_min is not null
),
median_ci as (
    select
        season, feature, seed_type,
        min(completion_min) filter (where r >= n / 2 - 0.98 * sqrt(n)) as median_lo,
        max(completion_min) filter (where r <= n / 2 + 0.98 * sqrt(n)) as median_hi
    from ranked
    group by all
)
select
    season,
    feature,
    seed_type,
    count(*) as matches,
    avg((outcome = 'completed')::int) as completion_rate,
    ci95(completion_rate, matches) as completion_ci,
    median(completion_min) as median_minutes,
    any_value(median_lo) as median_lo,
    any_value(median_hi) as median_hi,
    avg(won) filter (where outcome <> 'no result')
        - avg(predicted) filter (where outcome <> 'no result') as favorite_edge
from by_seed
join median_ci using (season, feature, seed_type)
group by all;
