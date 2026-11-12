#!/usr/bin/env python3
"""Summarise one run's dough-height series for the dashboard's "Past runs" card.

Usage: tools/summarize_run.py <run> [--title "Run 1: Weck jar, Oct 7-8"]
                               [--cycle K [--censored]]

  --cycle K    for a run where each jar was fed more than once: use only the K-th
               feed of each jar (feeds ordered by fed_at) and the frames from that
               feed up to the jar's next feed; outputs are named <run>_cK
  --censored   the cycle was cut off by the next feed before the peak, so ready,
               peak, lag, half rise and plateau are shown as not reached and the
               rise ratio as a lower bound

Reads   results/<run>_height.csv   (time_local, [jar], dough_height_px, ...;
                                            see tools/measure_heights.py)
        data/feeds.csv               (feed time, grams, flour, one row per jar)
Writes  results/<run>_summary.json
        www/starter/<run>.png              (chart of the smoothed series the numbers come from)
Prints  the markdown + picture cards to paste into dashboards/starter.yaml.

Definitions (fixed so every run and jar is measured the same way):
  smoothing      3-point rolling median of height relative to the start
  start height   mean of the first two frames
  rise ratio     smoothed maximum / start height
  time to peak   feed -> first time the smoothed series reaches its maximum
  lag            feed -> time the rise reaches 10% of the total rise (interpolated)
  half rise      feed -> time the rise reaches 50% of the total rise (interpolated)
  ready (90%)    feed -> time the rise reaches 90% of the total rise (interpolated);
                 the headline "ripe" time, since the peak itself sits on a flat
                 plateau and moves by hours between jars while this barely does
  80% of rise    same, at 80%; kept in the JSON as a cross-check, not on the card
  plateau        first time within 2% of the peak -> last frame still within 2%
                 (shown as "N h+" when the series ends while still on the plateau)
  weak rise      a rise ratio under 1.10 is within measurement noise of the
                 plateau band, so that jar's times are marked with * as unreliable
All times are measured from the feed time in the feed log.
"""
import csv, hashlib, json, os, statistics, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root
# The dashboard chart is written into the Home Assistant repo (www/starter/), which stays there.
HA_REPO = Path(os.environ.get("HA_REPO", Path.home() / "GIT" / "ha-repo"))
FMT = "%Y-%m-%d %H:%M"
WEAK = 1.10


def load(run, cycle=None):
    series = {}
    with open(ROOT / "results" / f"{run}_height.csv") as fh:
        for r in csv.DictReader(fh):
            jar = r.get("jar") or "1"
            series.setdefault(jar, []).append(
                (datetime.strptime(r["time_local"], FMT), float(r["dough_height_px"])))
    feeds = {}
    with open(ROOT / "data" / "feeds.csv") as fh:
        for r in csv.DictReader(fh):
            if r["run_id"] != run:
                continue
            feeds.setdefault(r["jar"], []).append(
                {**r, "run": r["run_id"], "position_left_to_right": r["position"],
                 "flour_type": r["flour_name"],
                 **{k: r[k][:-2] if r[k].endswith(".0") else r[k]
                    for k in ("starter_g", "flour_g", "water_g")}})
    feed = {}
    for jar, lst in feeds.items():
        lst.sort(key=lambda r: r["fed_at"])
        if cycle is None:
            feed[jar] = lst[-1]     # a run with several feeds of a jar keeps the last
            continue
        if len(lst) < cycle:
            sys.exit(f"jar {jar} has only {len(lst)} feed(s), no cycle {cycle}")
        feed[jar] = lst[cycle - 1]
        lo = datetime.strptime(lst[cycle - 1]["fed_at"], FMT)
        hi = datetime.strptime(lst[cycle]["fed_at"], FMT) if len(lst) > cycle else None
        if jar in series:
            series[jar] = [p for p in series[jar] if p[0] >= lo and (hi is None or p[0] < hi)]
    missing = [j for j in series if j not in feed]
    if missing:
        sys.exit(f"no data/feeds.csv row for run={run} jar={missing}")
    return series, feed


def median3(v):
    out = list(v)
    for i in range(1, len(v) - 1):
        out[i] = statistics.median(v[i - 1:i + 2])
    return out


def crossing(ts, ys, level):
    """First time the series reaches `level`, linearly interpolated."""
    for i in range(1, len(ys)):
        if ys[i] >= level > ys[i - 1]:
            f = (level - ys[i - 1]) / (ys[i] - ys[i - 1])
            return ts[i - 1] + (ts[i] - ts[i - 1]) * f
    return None


def hm(minutes):
    minutes = int(round(minutes / 5.0) * 5)          # nearest 5 min
    h, m = divmod(minutes, 60)
    if not h:
        return f"{m} min"
    return f"{h} h" if m == 0 else f"{h} h {m:02d} min"


def summarise_jar(jar, pts, feed, censored_cycle=False):
    ts = [p[0] for p in pts]
    start = statistics.mean([p[1] for p in pts[:2]])
    rel = [p[1] / start for p in pts]
    sm = median3(rel)
    fed = datetime.strptime(feed["fed_at"], FMT)

    peak = max(sm)
    t_peak = ts[sm.index(peak)]
    rise = peak - 1.0
    t_lag = crossing(ts, sm, 1.0 + 0.10 * rise)
    t_half = crossing(ts, sm, 1.0 + 0.50 * rise)
    t_80 = crossing(ts, sm, 1.0 + 0.80 * rise)
    t_90 = crossing(ts, sm, 1.0 + 0.90 * rise)
    first = next(i for i, y in enumerate(sm) if y >= 0.98 * peak)
    last = max(i for i, y in enumerate(sm) if y >= 0.98 * peak)
    plateau_min = (ts[last] - ts[first]).total_seconds() / 60
    censored = last == len(sm) - 1

    mins = lambda t: (t - fed).total_seconds() / 60
    out = {
        "jar": jar, "position": feed.get("position_left_to_right", ""), "fed_at": feed["fed_at"],
        "flour": feed["flour_type"],
        "starter_g": feed["starter_g"], "flour_g": feed["flour_g"], "water_g": feed["water_g"],
        "time_to_peak_min": round(mins(t_peak)),
        "lag_min": round(mins(t_lag)),
        "half_rise_min": round(mins(t_half)),
        "rise_80_min": round(mins(t_80)),
        "ready_90_min": round(mins(t_90)),
        "plateau_min": round(plateau_min), "plateau_still_going_at_end": censored,
        "rise_ratio": round(peak, 2),
        "weak_rise": peak < WEAK,
        "frames": len(pts),
        "cycle_censored": censored_cycle,
    }
    return out, ts, sm


FLOUR_LABEL = {"whole_wheat": "Whole wheat", "ap": "All-purpose", "blend": "50/50"}


def jar_label(s, mixed):
    """'Jar N (left)' when every jar has the same flour, else the flour name and position."""
    if mixed:
        fl = FLOUR_LABEL.get(s.get("flour_class", ""), s["flour"])
        return f"{fl} ({s['position']})" if s["position"] else fl
    return f"Jar {s['jar']}" + (f" ({s['position']})" if s["position"] else "")


def chart(run, jars, title, subtitle):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
    COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]          # categorical slots 1-3, in order
    multi = len(jars) > 1
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=130, facecolor=SURF)
    ax.set_facecolor(SURF)
    ymax = 1.7
    for k, (label, ts, rel) in enumerate(jars):
        ax.plot(ts, rel, color=COLORS[k % 3], lw=2, marker="o", ms=4 if multi else 5,
                mec=SURF, mew=1.2, zorder=3, label=label)
        ymax = max(ymax, max(rel) + 0.1)
    ts0, ts1 = jars[0][1][0], jars[0][1][-1]
    ax.set_ylim(0.9, ymax)
    ax.set_xlim(ts0, ts1 + (ts1 - ts0) * 0.02)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    span_h = (ts1 - ts0).total_seconds() / 3600
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2 if span_h <= 16 else 4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}×")
    days = (f"{ts0:%b} {ts0.day}" if ts0.date() == ts1.date()
            else f"{ts0:%b} {ts0.day} to {ts1:%b} {ts1.day}")
    ax.set_xlabel(f"Time of day ({days})", color=INK2, fontsize=10, labelpad=8)
    ax.set_ylabel("Dough height (× starting height)", color=INK2, fontsize=10, labelpad=8)
    fig.text(0.09, 0.96, title, color=INK, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.09, 0.895, subtitle, color=INK2, fontsize=9, ha="left", va="top")
    if multi:
        leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(jars), frameon=False,
                        fontsize=9, handlelength=1.6, borderaxespad=0.3)
        for t in leg.get_texts():
            t.set_color(INK2)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.76 if multi else 0.80, bottom=0.17)
    out = HA_REPO / "www" / "starter" / f"{run}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=SURF)
    return out


def cards(run, summaries, title):
    # ?v=<hash of the chart> so a re-rendered chart is never served from cache
    png = HA_REPO / "www" / "starter" / f"{run}.png"
    ver = hashlib.md5(png.read_bytes()).hexdigest()[:8]
    flours = sorted({s["flour"] for s in summaries})
    star = lambda s: "*" if s["weak_rise"] else ""
    plateau = lambda s: hm(s["plateau_min"]) + ("+" if s["plateau_still_going_at_end"] else "") + star(s)
    grams = lambda s: f"{s['starter_g']} g / {s['flour_g']} g / {s['water_g']} g"
    cen = any(s["cycle_censored"] for s in summaries)
    NR = "not reached"
    ready = lambda s: NR if cen else hm(s["ready_90_min"])
    peakt = lambda s: NR if cen else hm(s["time_to_peak_min"])
    lagt = lambda s: "n/a" if cen else hm(s["lag_min"])
    halft = lambda s: "n/a" if cen else hm(s["half_rise_min"])
    plat = lambda s: "n/a" if cen else plateau(s)
    rise = lambda s: (f"{s['rise_ratio']:.2f}× or more" if cen else f"{s['rise_ratio']:.2f}×")
    mixed = len(flours) > 1
    ind = " " * 14
    if len(summaries) == 1:
        s = summaries[0]
        body = "\n".join([
            f"{ind}| | |", f"{ind}|---|---|",
            f"{ind}| **Ready (90% of rise)** | **{ready(s)}**{star(s)} |",
            f"{ind}| Time to peak | {peakt(s)}{star(s)} |",
            f"{ind}| **Flour** | {s['flour']} |",
            f"{ind}| **Starter / flour / water** | {grams(s)} |",
            f"{ind}| Lag | {lagt(s)} |",
            f"{ind}| Time to half rise | {halft(s)} |",
            f"{ind}| Plateau | {plat(s)} |",
            f"{ind}| Rise ratio | {rise(s)} |",
        ])
    else:
        names = ([f"**{jar_label(s, True)}**" for s in summaries] if mixed else
                 [f"**Jar {s['jar']}**" + (f" ({s['position']})" if s["position"] else "") for s in summaries])
        row = lambda label, f: f"{ind}| {label} | " + " | ".join(f(s) for s in summaries) + " |"
        lines = []
        if len(flours) == 1:
            lines += [f"{ind}**Flour:** {flours[0]}", ""]
        lines += [f"{ind}| | " + " | ".join(names) + " |", f"{ind}|---|" + "---|" * len(summaries),
                  row("**Ready (90% of rise)**", lambda s: f"**{ready(s)}**{star(s)}"),
                  row("Time to peak", lambda s: peakt(s) + star(s))]
        if len(flours) > 1:
            lines.append(row("**Flour**", lambda s: s["flour"]))
        lines += [row("**Starter / flour / water**", grams),
                  row("Lag", lambda s: lagt(s) + star(s)),
                  row("Time to half rise", lambda s: halft(s) + star(s)),
                  row("Plateau", plat),
                  row("Rise ratio", rise)]
        if any(s["weak_rise"] for s in summaries):
            lines += ["", f"{ind}\\* rise under 10%: within measurement noise, so these times are unreliable"]
        body = "\n".join(lines)
    return f"""          - type: markdown
            content: |
              ### {title}
{body}
          - type: picture
            image: /local/starter/{run}.png?v={ver}
"""


def main(args):
    if not args or args[0].startswith("-"):
        sys.exit(__doc__)
    run = args[0]
    title = args[args.index("--title") + 1] if "--title" in args else run.replace("_", " ")
    cycle = int(args[args.index("--cycle") + 1]) if "--cycle" in args else None
    censored = "--censored" in args
    series, feed = load(run, cycle)
    if cycle:
        run = f"{run}_c{cycle}"                       # output file names
    order_pos = {"left": 0, "middle": 1, "right": 2}
    jars_sorted = sorted(series, key=lambda j: (order_pos.get(feed[j]["position_left_to_right"], 9), j))
    mixed = len({feed[j]["flour_type"] for j in series}) > 1
    summaries, plot = [], []
    for jar in jars_sorted:
        s, ts, sm = summarise_jar(jar, series[jar], feed[jar], censored)
        s["flour_class"] = feed[jar].get("flour_class", "")
        summaries.append(s)
        label = jar_label(s, mixed) if len(series) > 1 else ""
        plot.append((label, ts, sm))
    (ROOT / "results" / f"{run}_summary.json").write_text(
        json.dumps({"run": run, "jars": summaries}, indent=2) + "\n")

    order = jars_sorted
    fed = datetime.strptime(feed[order[0]]["fed_at"], FMT)
    vals = lambda k: [feed[j][k] for j in order]
    def amt(k):                 # one number if every jar got the same, else jar 1 / jar 2 / ...
        v = vals(k)
        return v[0] if len(set(v)) == 1 else " / ".join(v)
    amounts = " + ".join(f"{amt(k)} g {n}"
                         for k, n in (("starter_g", "starter"), ("flour_g", "flour"), ("water_g", "water")))
    each = " per jar" if len(series) > 1 else ""
    feds = sorted(datetime.strptime(feed[j]["fed_at"], FMT) for j in order)
    fed_txt = (f"{fed:%b} {fed.day}, {fed.strftime('%-I:%M %p')}" if feds[0] == feds[-1] else
               f"{feds[0]:%b} {feds[0].day}, {feds[0].strftime('%-I:%M')} to {feds[-1].strftime('%-I:%M %p')}")
    flours_txt = "; ".join(sorted(set(vals('flour_type')))) if not mixed else "Left to right as in the legend"
    subtitle = f"{flours_txt} · {amounts}{each} · fed {fed_txt}"
    chart(run, plot, title, subtitle)
    print(cards(run, summaries, title))


if __name__ == "__main__":
    main(sys.argv[1:])
