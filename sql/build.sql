-- Tables built from the raw API files in ~/mcsr-data (downloaded by fetch_data.py).
-- Every match involves at least one top-150 player; matches between two of them
-- appear in both players' lists, hence the de-duplication.

create temp table raw as
select distinct on (id) *
from read_json('~/mcsr-data/season-*/match-lists/*.json', format = 'array', union_by_name = true);

-- One row per match.
create table matches as
select
    season,
    id as match_id,
    to_timestamp(date) as played_at,
    seed.overworld,
    seed.nether as bastion,
    seed.variations,
    result.uuid as winner_uuid,
    case
        when result.uuid is null then 'no result'
        when forfeited then 'forfeit'
        else 'completed'
    end as outcome,
    case when not forfeited then result.time / 60000 end as completion_min
from raw;

-- One row per player per match. elo_before is the rating going into the match.
create table match_players as
select
    r.season,
    r.id as match_id,
    c.uuid,
    p.nickname,
    c.eloRate as elo_before,
    c.change as elo_change,
    c.uuid = r.result.uuid as won
from raw r, unnest(r.changes) as t(c), unnest(r.players) as u(p)
where c.uuid = p.uuid;

-- Half-width of a 95% confidence interval for a proportion.
create macro ci95(p, n) as 1.96 * sqrt(p * (1 - p) / n);
