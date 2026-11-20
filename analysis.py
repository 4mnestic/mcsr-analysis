"""Build the tables, run the analyses, and save the charts in figures/."""
import duckdb
import matplotlib.pyplot as plt

BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#1f1f1e", "#8a8a85"
plt.rcParams.update({
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": "#e6e6e3", "grid.linewidth": 0.6, "figure.dpi": 150,
})

con = duckdb.connect()
for name in ["build", "elo_calibration", "seed_balance"]:
    con.execute(open(f"sql/{name}.sql").read())

seasons = [s for (s,) in con.sql("select distinct season from matches order by season desc").fetchall()]
colors = dict(zip(seasons, [BLUE, ORANGE]))


def save(fig, name, top=1.0):
    fig.tight_layout(rect=(0, 0, 1, top))
    fig.savefig(f"figures/{name}.png", facecolor="white")
    plt.close(fig)


# 1. Calibration: predicted vs. actual favorite win rate.
cal = con.sql("select * from calibration where matches >= 100 order by season, bin").df()
fig, ax = plt.subplots(figsize=(5, 4.5))
ax.plot([0.5, 0.9], [0.5, 0.9], color=MUTED, lw=1, ls="--")
for season in seasons:
    d = cal[cal.season == season]
    ax.errorbar(d.predicted, d.actual, yerr=d.ci, fmt="o-", ms=5, lw=1.5, capsize=0,
                color=colors[season], label=f"Season {season}")
ax.set(xlabel="Predicted favorite win rate", ylabel="Actual favorite win rate",
       xlim=(0.48, 0.9), ylim=(0.48, 0.9), aspect="equal")
ax.legend(frameon=False, loc="upper left")
save(fig, "calibration")

# 2. Abandonment: close vs. lopsided matches, overall and within skill levels.
mq = con.sql(f"select * from match_quality where season = {seasons[0]}").df()
levels = ["all matches", "< 1500", "1500–1800", "1800+"]
fig, ax = plt.subplots(figsize=(6, 3.5))
for offset, (closeness, color) in zip([-0.12, 0.12], [("close", BLUE), ("lopsided", ORANGE)]):
    d = mq[mq.closeness == closeness].set_index("skill_level").reindex(levels)
    ax.errorbar([i + offset for i in range(len(levels))], d.abandonment_rate, yerr=d.ci,
                fmt="o", ms=6, capsize=0, color=color, label=f"{closeness} matches")
ax.axvline(0.5, color=MUTED, lw=0.8)
ax.set_xticks(range(len(levels)), [levels[0], *(f"Elo {lvl}" for lvl in levels[1:])])
ax.set(ylabel="Abandoned (forfeit or no result)")
ax.yaxis.set_major_formatter(lambda y, _: f"{y:.0%}")
ax.legend(frameon=False)
save(fig, "abandonment")

# 3. Seed balance: median completion time by seed type.
sb = con.sql(f"""
    select s.* from seed_balance s
    join (select feature, seed_type, median_minutes as sort_key from seed_balance where season = {seasons[0]})
        using (feature, seed_type)
    order by season, feature, sort_key desc""").df()
fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharex=True)
for ax, feature in zip(axes, ["overworld", "bastion"]):
    for offset, season in zip([-0.12, 0.12], seasons):
        d = sb[(sb.feature == feature) & (sb.season == season)]
        y = [i + offset for i in range(len(d))]
        ax.errorbar(d.median_minutes, y, xerr=[d.median_minutes - d.median_lo, d.median_hi - d.median_minutes],
                    fmt="o", ms=5, capsize=0, color=colors[season], label=f"Season {season}")
    ax.set_yticks(range(len(d)), [t.replace("_", " ").lower() for t in d.seed_type])
    ax.set_title(f"{feature.capitalize()} type", color=INK, loc="left")
    ax.set_xlabel("Median completion time (min)")
fig.legend(*axes[0].get_legend_handles_labels(), frameon=False, loc="upper center", ncol=2)
save(fig, "seed_completion_time", top=0.9)

# Numbers quoted in the reports.
print(con.sql("""
    select season, count(*) matches, min(played_at)::date first_match, max(played_at)::date last_match,
           round(avg((outcome = 'completed')::int), 3) completion_rate, round(median(completion_min), 2) median_minutes
    from matches group by 1 order by 1"""))
print(con.sql("""
    select season, round(sum(abs(actual - predicted) * matches) / sum(matches), 4) mean_abs_error,
           round(sum(matches) filter (where bin >= 0.75) / sum(matches), 3) share_predicted_75_plus
    from calibration group by 1 order by 1"""))
print(con.sql("select season, round(avg((predicted < 0.6)::int), 3) share_close from favorites group by 1 order by 1"))
print(con.sql("select * exclude (season), season from calibration order by season, bin"))
print(con.sql("select * from match_quality order by season, skill_level, closeness"))
print(con.sql("""
    select season, feature, seed_type, matches, round(avg_match_elo) avg_match_elo,
           round(avg_predicted, 3) avg_predicted, round(completion_rate, 3) completion_rate,
           round(median_minutes, 2) median_minutes, round(favorite_edge, 3) favorite_edge
    from seed_balance order by season, feature, seed_type"""))
