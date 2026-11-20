#!/usr/bin/env python3
"""Watch mode: tell Kris when a starter or levain has peaked, from the pantry timelapse.

Run on a timer (starter-watch.timer (installed by tools/install-watch.sh)), once just after each frame. Each run:
  1. asks the HA machine whether watch mode is on (the folder /media/starter/watch
     exists only while input_boolean.starter_watch is on; HA deletes it when it goes off)
  2. pulls any new frames into ~/.cache/starter-watch/
  3. finds the Weck jar (starter rig: fixed columns; old Reolink frames: by shape,
     tools/jar_template.png), tracks the dough height, and
     works from the rate of change, so it needs no feed time and can start mid-rise
  4. sends at most one "nearly there" and one "peaked" phone notification per session
     through the HA webhook whose URL is in tools/watch_secret (gitignored), and a
     heartbeat after every good run; HA texts Kris if the heartbeat stops
  5. saves the pantry temperature (HA 5-minute statistics, read-only over ssh) for the
     session to ~/.cache/starter-watch/temperature.csv; archived with the frames
  6. draws the height chart (~/.cache/starter-watch/chart.png) and copies it to HA at
     /config/www/starter/live/watch.png for the Starter dashboard
  Problems with the watcher itself (ssh, rsync, webhook, a crash) go to dunst via
  notify-send, repeats held back for 2 h.

Usage:
  tools/watch_service.py                        normal timer run
  tools/watch_service.py --dry-run              as above but print instead of POSTing
  tools/watch_service.py --replay DIR [--jar x0-x1] [--every N]
                                                  replay saved frames in order (no network),
                                                  print when each alert would have fired;
                                                  --every N uses every Nth frame (to mimic
                                                  the 30 min watch cadence on a denser run)
                                                  --chart OUT.png also draws the height chart
  tools/watch_service.py --save-temps photos/watch_<first frame>
                                                  add the pantry temperature to an archived session

Alert rules (ballpark on purpose, not for experiments; see tools/measure_heights.py
and tools/summarize_run.py for the experiment-grade measurement):
  height          dough height in pixels, 3-point median
  rise            (max - min) / min of the smoothed height; must reach 8% before any alert
  slope           linear fit of the smoothed height over the last 90 min, as fraction of
                  current height per hour
  nearly there    slope has fallen to 25% of the largest slope seen, still rising
  peaked          the last two smoothed heights are 2% or more below the maximum
                  (and at least 2 h of frames, so an early bump can't trigger it)
  settle          the first 45 min of frames are ignored: the jar has just been handled
                  and freshly fed dough settles, which looks like a peak
  noise gate      no alert unless the smoothed rise is at least 5x the frame-to-frame
                  noise of the raw heights (each height against the mean of its two
                  neighbours, so a steady rise doesn't count as noise). Real runs score
                  30x or more; a surface the detector can't hold scores below 1x
  bump            starter rig only: the jar glass above the dough and the nest collar
                  are compared with the previous measured frame. If both change (the
                  jar was turned, lifted or knocked), a new segment starts there: its
                  heights get their own bottom and are shifted to carry on from the
                  last height before the bump, so the jump isn't read as a rise or fall
"""
import json, shutil, subprocess, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_heights import colourfulness, measure_jar  # noqa: E402

HERE = Path(__file__).resolve().parent
HOST, REMOTE = "ha", "/media/starter/watch"
CACHE = Path.home() / ".cache" / "starter-watch"
SECRET = HERE / "watch_secret"

# Two cameras, told apart by frame width so old runs still replay:
#   Reolink (until 2026-11-19): wide pantry view, jar found by shape, colour skip
#   starter rig (ESP32-CAM, 1600x1200): jar fixed in the nest, so fixed columns;
#     weaker colour; no infrared mode, so a dark frame means the light was off
RIG_WIDTH = 1600
RIG_COLS = (600, 1000)          # middle of the jar's glass, clear of the edge refraction
RIG_ROWS = (300, 1150)          # mid-jar down to the nest (calibrated 2026-11-19)
RIG_WARM = 5                    # red-minus-blue that counts as dough on this camera
RIG_DARK = 25                   # mean brightness below this = light was off; skip
# bump check: (rows, cols) that change when the jar is turned or moved but not as the
# dough rises; similarity to the previous frame is about 0.99 when untouched and 0.7
# after the jar was moved (2026-11-19)
RIG_BUMP_REGIONS = (((20, 280), (450, 1150)),     # jar glass above the dough
                    ((1080, 1200), (380, 1260)))  # nest collar
BUMP_NCC = 0.93                 # a jar move = every bump region below this
ROWS = (1500, 2000)             # Reolink: band of the frame that contains the jars
SEARCH = (800, 3500)            # Reolink: columns to search for the jar
TEMPLATE = HERE / "jar_template.png"   # rim and upper glass of the Weck jar
TEMPLATE_SEARCH_ROWS = (1000, 1800)   # rows searched for the jar's rim
TEMPLATE_MIN_SCORE = 0.35       # loose: only rules out nonsense; the jar always scores 0.4+ on a new background
GIVE_UP_MIN = 360               # minutes of frames without finding a jar before saying so
RISE_MIN = 0.08
NEAR_FRACTION = 0.25
PEAK_DROP = 0.02
SLOPE_WINDOW_MIN = 90
MAX_STEP = 0.10                 # one frame can't move the height by more than this fraction (a surface mis-read, not a rise)
NEAR_FRAMES = 3                 # "nearly there" must hold for this many frames in a row
SETTLE_MIN = 45
NOISE_K = 5                     # smoothed rise must be this many times the height noise


# ---------------------------------------------------------------- measuring

def frame_time(f):
    return datetime.strptime(Path(f).name[:13], "%Y%m%d_%H%M")


def load(f):
    return np.asarray(Image.open(f).convert("RGB"), dtype=float)


def _gray4(a):
    """Grayscale, shrunk 4x by block averaging (a is a float RGB array or 2-D gray)."""
    g = a if a.ndim == 2 else a.mean(axis=2)
    h, w = g.shape[0] // 4 * 4, g.shape[1] // 4 * 4
    return g[:h, :w].reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3))


def match_jar(frame):
    """Find the jar by shape: best match of tools/jar_template.png (the rim and upper
    glass of the Weck jar, taken from the pantry camera). Returns ((x0, x1), score):
    full-frame columns and the match quality. The camera is fixed, so this
    only has to cope with the jar being set down a little differently each time."""
    t = _gray4(np.asarray(Image.open(TEMPLATE).convert("L"), dtype=float))
    th, tw = t.shape
    y0, y1 = TEMPLATE_SEARCH_ROWS
    img = _gray4(frame[y0:y1, SEARCH[0]:SEARCH[1]])
    t0 = t - t.mean()
    # normalised cross-correlation by FFT; window sums from an integral image
    H, W = img.shape
    F = np.fft.rfft2(img, (H + th, W + tw))
    G = np.fft.rfft2(t0[::-1, ::-1], (H + th, W + tw))
    num = np.fft.irfft2(F * G, (H + th, W + tw))[th - 1:H, tw - 1:W]
    ii = np.pad(img, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ii2 = np.pad(img ** 2, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def win(m):
        return m[th:, tw:] - m[:-th, tw:] - m[th:, :-tw] + m[:-th, :-tw]
    n = th * tw
    var = win(ii2) - win(ii) ** 2 / n
    ncc = num / np.sqrt(np.maximum(var, 1e-6) * (t0 ** 2).sum())
    iy, ix = np.unravel_index(np.argmax(ncc), ncc.shape)
    x0 = SEARCH[0] + ix * 4
    return (int(x0), int(x0 + tw * 4)), float(ncc[iy, ix])


def is_rig(a):
    return a.shape[1] <= RIG_WIDTH


def unusable(a):
    """Frame can't be measured: a dark rig frame, or a Reolink night (infrared) frame."""
    return a.mean() < RIG_DARK if is_rig(a) else colourfulness(a) < 3


def locate(frame):
    band, score = match_jar(frame)
    return band if score >= TEMPLATE_MIN_SCORE else None


def limit_steps(v, max_step=MAX_STEP):
    """Cap how far one frame can move the height, so a surface mis-read (the detector
    catching smear on the glass) can't pass as a fast rise. A real change still gets
    through, a few frames late."""
    out = [float(np.median(v[:3]))]     # start from the middle of the first few, not one frame
    for y in v:
        lo, hi = out[-1] * (1 - max_step), out[-1] * (1 + max_step)
        out.append(min(max(float(y), lo), hi))
    return out[1:]


def similarity(a, b):
    """Normalised correlation of two same-size gray patches (1 = identical up to exposure)."""
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 1.0


def moved(prev, cur):
    """True if the jar was turned, lifted or knocked between two rig frames: every
    bump region looks different, not just the part the dough rises through."""
    g0, g1 = _gray4(prev), _gray4(cur)
    for (y0, y1), (x0, x1) in RIG_BUMP_REGIONS:
        r = (slice(y0 // 4, y1 // 4), slice(x0 // 4, x1 // 4))
        if similarity(g0[r], g1[r]) >= BUMP_NCC:
            return False
    return True


def noise_px(heights):
    """Frame-to-frame noise of the raw heights in px: each height against the mean of
    its neighbours (a steady trend cancels), robust sigma via the median."""
    h = np.asarray(heights, dtype=float)
    if len(h) < 3:
        return 0.0
    r = h[1:-1] - (h[:-2] + h[2:]) / 2
    return float(1.4826 * np.median(np.abs(r)) / np.sqrt(1.5))


def segment_heights(stems, meas, bumps):
    """Heights in px for the measured frames, split into segments at each bump. Each
    segment uses its own bottom, and is shifted to start where the previous one ended."""
    segs = []
    for s in stems:
        if not segs or s in bumps:
            segs.append([])
        segs[-1].append(s)
    out = []
    for seg in segs:
        bot = float(np.median([meas[s][1] for s in seg]))
        h = [bot - meas[s][0] for s in seg]
        if out:
            off = out[-1] - h[0]
            h = [y + off for y in h]
        out += h
    return out


def median3(v):
    out = list(v)
    for i in range(1, len(v) - 1):
        out[i] = float(np.median(v[i - 1:i + 2]))
    return out


# ---------------------------------------------------------------- projection
# Feed-agnostic forecast from the frames alone. The session start (watch mode turned
# on, normally right at the feed) stands in for the feed time. The rise is modelled
# as a logistic curve, h(t) = b * (1 + R * S((t - t_half) / w)), the shape that
# logistic growth of the culture gives. Before the rise shows, the forecast is the
# prior below; each frame then reweights every candidate curve by how well it fits.
# Priors from the 10 completed jars in results/*_summary.json (2026-10/11, whole
# wheat and AP, 100% hydration, about 70F): half rise 4.4-10.4 h after the feed
# (geometric mean 6.9 h); ready (90% of the rise) 2.4-5.5 h after half rise, so
# w = (ready - half) / 2.2 = 1.1-2.5 h; rise 1.26-2.14x. Widened for fridge starters.
PRIOR_HALF_H = (6.9, 0.35)      # (median h, log sd)
PRIOR_W_H = (1.35, 0.35)
PRIOR_RISE = (0.5, 0.6)         # R = rise ratio - 1
READY_Z = 2.197                 # S = 0.9 at t_half + 2.197 w
NOISE_FLOOR = 0.04              # never trust a fit tighter than this share of the height
LIK_NU = 3                      # Student-t degrees of freedom for frame residuals


def _lognorm(x, med, sd):
    return -((np.log(x) - np.log(med)) ** 2) / (2 * sd * sd) - np.log(x)


def project(hours, heights, noise):
    """Forecast from frames so far. hours: since the session started; heights: px
    (may be empty). Returns ready-time quantiles (h since start) and a sampler for
    projected curves, as {'ready': (q10, q50, q90), 'curves': fn(t) -> (lo, mid, hi)
    relative to the fitted start height, 'n': frames used}."""
    th = np.arange(1.0, 24.01, 0.25)
    ww = np.geomspace(0.5, 4.0, 16)
    rr = np.geomspace(0.08, 2.0, 28)
    T, W, R = np.meshgrid(th, ww, rr, indexing="ij")
    T, W, R = T.ravel(), W.ravel(), R.ravel()
    logp = (_lognorm(T, *PRIOR_HALF_H) + _lognorm(W, *PRIOR_W_H) + _lognorm(R, *PRIOR_RISE))
    t = np.asarray(hours, dtype=float)
    y = np.asarray(heights, dtype=float)
    B = np.ones_like(T)
    if len(y) >= 3:
        f = 1 + R[:, None] / (1 + np.exp(-(t[None, :] - T[:, None]) / W[:, None]))
        B = (f * y).sum(1) / (f * f).sum(1)
        sig = max(noise, NOISE_FLOOR * float(np.median(y)))
        r2 = ((y - B[:, None] * f) / sig) ** 2
        # Student-t, not Gaussian: a detector jump or a stuck reading then pulls the
        # fit less than a run of ordinary frames
        logp = logp - ((LIK_NU + 1) / 2 * np.log1p(r2 / LIK_NU)).sum(1)
    wt = np.exp(logp - logp.max())
    wt /= wt.sum()
    ready = T + READY_Z * W

    def q(v, ps):
        o = np.argsort(v)
        c = np.cumsum(wt[o])
        return [float(v[o][np.searchsorted(c, p)]) for p in ps]
    idx = np.random.default_rng(0).choice(len(wt), size=400, p=wt)
    b0 = np.median(y[:3]) if len(y) >= 3 else 1.0

    def curves(tt):
        tt = np.asarray(tt, dtype=float)
        c = B[idx, None] * (1 + R[idx, None] / (1 + np.exp(-(tt[None, :] - T[idx, None]) / W[idx, None])))
        c = c / b0 if len(y) >= 3 else 1 + R[idx, None] / (1 + np.exp(-(tt[None, :] - T[idx, None]) / W[idx, None]))
        return np.percentile(c, [10, 50, 90], axis=0)
    return {"ready": tuple(q(ready, [0.1, 0.5, 0.9])), "curves": curves, "n": int(len(y))}


# ---------------------------------------------------------------- the decision

def rolling_slopes(ts, sm):
    """Per-index slope (fraction of current height per hour) over the last window."""
    out = []
    for i in range(len(sm)):
        pts = [(t, y) for t, y in zip(ts[:i + 1], sm[:i + 1]) if ts[i] - t <= SLOPE_WINDOW_MIN]
        if len(pts) < 3:
            out.append(None)
            continue
        x = np.array([p[0] for p in pts]) / 60.0
        y = np.array([p[1] for p in pts])
        out.append(float(np.polyfit(x, y, 1)[0] / sm[i]))
    return out


def analyse(ts, heights):
    """ts in minutes, heights in px. The smoothed series and the numbers the alerts
    (and the chart) work from, or None before there are 4 frames past the settle."""
    keep = [i for i, t in enumerate(ts) if t - ts[0] >= SETTLE_MIN]
    ts, heights = [ts[i] for i in keep], [heights[i] for i in keep]
    if len(heights) < 4:
        return None
    ts = [t - ts[0] + SETTLE_MIN for t in ts]
    sm = median3(limit_steps(heights))
    top, low = max(sm), min(sm)
    noise = noise_px(heights)
    i_top = sm.index(top)
    hrs = (ts[-1] - ts[0]) / 60.0
    return {
        "keep": keep, "ts": ts, "sm": sm, "top": top, "low": low, "i_top": i_top,
        "rise": (top - low) / low, "noise": noise,
        "clear": (top - low) / low >= RISE_MIN and top - low >= NOISE_K * noise,
        # two points in a row below the top, and enough history, so one noisy frame
        # or a bumped camera early on can't call a peak
        "peaked": (len(sm) >= 6 and hrs >= 2 and i_top <= len(sm) - 3
                   and all(y <= top * (1 - PEAK_DROP) for y in sm[-2:])),
    }


def decide(ts, heights, sent):
    """ts in minutes, heights in px. Returns a list of (key, title, message)."""
    a = analyse(ts, heights)
    if a is None or not a["clear"]:
        return []
    ts, sm, top, rise, i_top, peaked = a["ts"], a["sm"], a["top"], a["rise"], a["i_top"], a["peaked"]
    slopes = rolling_slopes(ts, sm)
    known = [s for s in slopes if s is not None]
    events = []
    if peaked and "peaked" not in sent:
        ago = (ts[-1] - ts[i_top]) / 60.0
        events.append(("peaked", "Starter has peaked",
                       f"Up {rise * 100:.0f}% overall; the top was about {ago:.1f} h ago "
                       f"and it is now {100 * (1 - sm[-1] / top):.0f}% down."))
    elif not peaked and "near" not in sent and known:
        best = max(known)
        cur = known[-1]
        # slowed for several frames running, each judged against the fastest rate seen
        # up to that frame, so one odd frame can't trigger it
        slowed = len(known) >= NEAR_FRAMES and all(
            max(known[:j + 1]) > 0.01 and abs(known[j]) <= NEAR_FRACTION * max(known[:j + 1])
            for j in range(len(known) - NEAR_FRAMES, len(known)))
        if slowed:
            events.append(("near", "Starter is nearly there",
                           f"Rise has slowed to {100 * cur / best:.0f}% of its fastest "
                           f"({rise * 100:.0f}% up so far); it is getting close."))
    return events


# ---------------------------------------------------------------- state / session

class Session:
    """Everything remembered about one watch session; stored as JSON in the cache."""

    def __init__(self, data=None):
        d = data or {}
        self.jar = d.get("jar")                 # [x0, x1] once accepted
        self.meas = d.get("meas", {})           # stem -> [surface, bottom]
        self.sent = d.get("sent", [])
        self.skipped = d.get("skipped", [])     # non-colour frames
        self.bumps = d.get("bumps", [])         # frames where a new segment starts (jar moved)

    def dump(self):
        return {"jar": self.jar, "meas": self.meas, "sent": self.sent,
                "skipped": self.skipped, "bumps": self.bumps}


def step(sess, files, forced_jar=None):
    """Process the frames seen so far; returns events to send. Mutates sess."""
    colour = [f for f in files if f.stem not in sess.skipped]

    if sess.jar is None:
        if forced_jar:
            sess.jar = list(forced_jar)
        elif colour:
            a = load(colour[-1])
            if unusable(a):                 # dark / infrared frame: shape match is unreliable
                sess.skipped.append(colour[-1].stem)
                return []
            band = RIG_COLS if is_rig(a) else locate(a)
            if band:
                sess.jar = list(band)
            else:
                if (frame_time(colour[-1]) - frame_time(colour[0])).total_seconds() / 60 >= GIVE_UP_MIN and "nojar" not in sess.sent:
                    return [("nojar", "Starter watch: can't find the jar",
                             "The Weck jar isn't where the camera expects it. Is it in view?")]
                return []

    if sess.jar is None:
        return []
    x0, x1 = sess.jar
    by_stem = {f.stem: f for f in files}
    prev = None                 # last measured frame, for the bump check
    prev_stem = next(reversed(sess.meas), None)
    for f in colour:
        if f.stem in sess.meas:
            continue
        a = load(f)
        if unusable(a):
            sess.skipped.append(f.stem)
            continue
        try:
            if is_rig(a):
                s, b = measure_jar(a, x0, x1, *RIG_ROWS, warm=RIG_WARM)
            else:
                s, b = measure_jar(a, x0, x1, *ROWS)
        except ValueError:      # no warm pixels in the box at all
            sess.skipped.append(f.stem)
            continue
        if is_rig(a) and prev_stem is not None:
            if prev is None and prev_stem in by_stem:
                prev = load(by_stem[prev_stem])
            if prev is not None and moved(prev, a):
                sess.bumps.append(f.stem)
        sess.meas[f.stem] = [int(s), int(b)]
        prev, prev_stem = a, f.stem

    stems = [f.stem for f in colour if f.stem in sess.meas]
    if not stems:
        return []
    heights = segment_heights(stems, sess.meas, set(sess.bumps))
    t0 = frame_time(Path(stems[0] + ".jpg"))
    ts = [(frame_time(Path(s + ".jpg")) - t0).total_seconds() / 60.0 for s in stems]
    sess.series = (stems, ts, heights)
    return [e for e in decide(ts, heights, set(sess.sent)) if e[0] not in sess.sent]


# ---------------------------------------------------------------- chart

CHART_REMOTE = "/config/www/starter/live/watch.png"   # gitignored in the HA repo
CHART_GITIGNORE = "www/starter/live/"


def chart(sess, out):
    """Height since the session started (the jar went into the rig), as the alerts see
    it: raw frames as dots, the smoothed line, a band of +/- the frame-to-frame noise,
    dotted lines at the top (time and total rise) once the rise is clear, and until the
    peak a forecast (dashed curve, 80% band, ready-time window) from project()."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import timedelta
    SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
    BLUE, ORANGE, MUTED = "#2a78d6", "#eb6834", "#a3a29d"
    stems, ts, heights = getattr(sess, "series", ([], [], []))
    times = [frame_time(Path(s + ".jpg")) for s in stems]
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=130, facecolor=SURF)
    ax.set_facecolor(SURF)
    a = analyse(ts, heights) if stems else None
    ys = [1.0]
    title, sub = "Starter height: waiting for frames", ""
    done = a is not None and (a["peaked"] or "peaked" in sess.sent)
    if a is not None:
        base = a["sm"][0]
        kt = [times[i] for i in a["keep"]]
        rel = [y / base for y in a["sm"]]
        band = a["noise"] / base
        early = [i for i in range(len(stems)) if i not in a["keep"]]
        ax.plot([times[i] for i in early], [heights[i] / base for i in early], "o",
                mfc="none", mec=MUTED, ms=4, zorder=2, label=f"first {SETTLE_MIN} min")
        ax.plot(kt, [heights[i] / base for i in a["keep"]], "o", color=BLUE, alpha=0.35,
                ms=3.5, mew=0, zorder=2, label="each frame")
        ax.fill_between(kt, [r - band for r in rel], [r + band for r in rel], color=BLUE,
                        alpha=0.12, lw=0, zorder=1, label="± frame noise")
        ax.plot(kt, rel, color=BLUE, lw=2, zorder=3, label="height")
        ys += [r + band for r in rel] + [r - band for r in rel] + [h / base for h in heights]
        for b in sess.bumps:
            tb = frame_time(Path(b + ".jpg"))
            ax.axvline(tb, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
            ax.annotate("jar moved", (tb, 0), xycoords=("data", "axes fraction"),
                        xytext=(3, 6), textcoords="offset points", color=INK2, fontsize=8)
        top_rel = a["top"] / base
        if a["clear"]:
            tt = kt[a["i_top"]]
            ax.axvline(tt, color=INK2, lw=1.2, ls=":", zorder=4)
            ax.axhline(top_rel, color=INK2, lw=1.2, ls=":", zorder=4)
            ax.annotate(f"{'peak' if done else 'highest so far'} {tt:%-I:%M %p}", (tt, 0),
                        xycoords=("data", "axes fraction"), xytext=(4, 6),
                        textcoords="offset points", color=INK, fontsize=9)
            ax.annotate(f"total rise {a['rise'] * 100:.0f}%", (1, top_rel),
                        xycoords=("axes fraction", "data"), xytext=(-4, 4), ha="right",
                        textcoords="offset points", color=INK, fontsize=9)
            ys.append(top_rel * 1.05)
        if done:
            title = "Starter has peaked"
            sub = f"Up {a['rise'] * 100:.0f}%; frames vary ±{band * 100:.0f}% around the line."
        elif not a["clear"]:
            sub = (f"No clear rise yet: {a['rise'] * 100:.0f}% so far, frames vary ±{band * 100:.0f}%. ")
        else:
            sub = f"Up {a['rise'] * 100:.0f}% so far; frames vary ±{band * 100:.0f}%. "
    if times and not done:
        t0 = times[0]
        if a is not None:
            hrs = [ts[i] / 60.0 for i in a["keep"]]
            p = project(hrs, [heights[i] for i in a["keep"]], a["noise"])
            last_h = hrs[-1]
        else:
            p = project([], [], 0.0)
            last_h = ts[-1] / 60.0 if ts else 0.0
        q10, q50, q90 = p["ready"]
        at = lambda h: t0 + timedelta(hours=float(h))
        fut = np.linspace(last_h, max(last_h + 0.5, min(q90 + 1.5, 30.0)), 60)
        lo, mid, hi = p["curves"](fut)
        ft = [at(h) for h in fut]
        ax.fill_between(ft, lo, hi, color=ORANGE, alpha=0.12, lw=0, zorder=1, label="forecast, 80%")
        ax.plot(ft, mid, color=ORANGE, lw=1.6, ls="--", zorder=3, label="forecast")
        ax.axvspan(at(q10), at(q90), color=ORANGE, alpha=0.07, lw=0, zorder=0)
        ax.axvline(at(q50), color=ORANGE, lw=1.2, ls=":", zorder=4)
        ax.annotate(f"ready ~{at(q50):%-I:%M %p}", (at(q50), 1), xycoords=("data", "axes fraction"),
                    xytext=(4, -14), textcoords="offset points", color=ORANGE, fontsize=9)
        ys += list(hi) + list(lo)
        title = f"Ready around {at(q50):%-I:%M %p}"
        src = (f"from {p['n']} frames" if p["n"] >= 3 else
               "from past runs only; it narrows once the rise shows")
        sub += f"Ready between {at(q10):%-I:%M %p} and {at(q90):%-I:%M %p} (80%), {src}."
        times_end = at(fut[-1])
    else:
        times_end = times[-1] if times else None
    if times:
        span = max(times_end - times[0], timedelta(hours=2))
        ax.set_xlim(times[0] - span * 0.02, times[0] + span * 1.03)
        h = span.total_seconds() / 3600
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1 if h <= 6 else 2 if h <= 16 else 4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
        ax.set_ylim(min(0.9, min(ys) - 0.05), max(1.3, max(ys) + 0.05))
        leg = ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), frameon=False, fontsize=8,
                        ncol=6, handlelength=1.4, columnspacing=1.0, borderaxespad=0.2)
        for t in leg.get_texts():
            t.set_color(INK2)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}×")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    start = f"since {times[0]:%a %-I:%M %p}" if times else ""
    last = f"; last frame {times[-1]:%a %-I:%M %p}" if times else ""
    ax.set_xlabel(f"Time of day ({start}{last})", color=INK2, fontsize=10, labelpad=8)
    ax.set_ylabel("Height (× first height)", color=INK2, fontsize=10, labelpad=8)
    fig.text(0.09, 0.96, title, color=INK, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.09, 0.895, sub, color=INK2, fontsize=9, ha="left", va="top")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.76, bottom=0.17)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=SURF)
    plt.close(fig)
    return out


def upload_chart(png):
    """Copy the chart to HA's www, only once the HA checkout ignores that folder (so
    ha-sync never commits it). Best effort: a failure here never blocks the alerts."""
    cmd = (f"grep -qxF '{CHART_GITIGNORE}' /config/.gitignore || exit 3; "
           f"mkdir -p {Path(CHART_REMOTE).parent} && cat > {CHART_REMOTE}.tmp "
           f"&& mv {CHART_REMOTE}.tmp {CHART_REMOTE}")
    try:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=8", HOST, cmd], input=png.read_bytes(),
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"chart upload failed: {e}", file=sys.stderr)
        return
    if r.returncode == 3:
        print(f"chart not uploaded: HA's .gitignore has no {CHART_GITIGNORE} yet (pull ha-repo there)")
    elif r.returncode != 0:
        print(f"chart upload failed: {r.stderr.decode()[:200]}", file=sys.stderr)


# ---------------------------------------------------------------- outside world

def ssh(cmd):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=8", HOST, cmd],
                          capture_output=True, text=True, timeout=60)


def webhook(payload):
    """POST JSON to the HA webhook; True on success."""
    if not SECRET.exists():
        print("no tools/watch_secret; not sending", file=sys.stderr)
        return False
    req = urllib.request.Request(
        SECRET.read_text().strip(), data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
        return True
    except OSError as e:
        print(f"webhook failed: {e}", file=sys.stderr)
        return False


def post(title, message, dry):
    print(f"ALERT: {title} - {message}")
    return True if dry else webhook({"title": title, "message": message})


def desktop_error(message):
    """Tell the person at this machine (dunst) that the watcher itself is failing.

    Repeats of the same error are held back for 2 h so a long outage doesn't spam.
    Best effort: silent if notify-send is missing.
    """
    print(f"ERROR: {message}", file=sys.stderr)
    CACHE.mkdir(parents=True, exist_ok=True)
    marker = CACHE / "last_error.json"
    try:
        last = json.loads(marker.read_text())
    except (OSError, ValueError):
        last = {}
    now = datetime.now().timestamp()
    if last.get("message") == message and now - last.get("at", 0) < 7200:
        return
    marker.write_text(json.dumps({"message": message, "at": now}))
    try:
        subprocess.run(["notify-send", "-u", "critical", "-a", "starter-watch",
                        "Starter watch problem", message], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


TEMP_SENSOR = "sensor.pantry_temperature_sensor_temperature"
TEMP_HEADER = "time_local,period,mean_f,min_f,max_f"


def pull_temperature(start, end):
    """Pantry temperature statistics from HA's recorder database between two local
    datetimes, read-only over ssh: 5-minute rows (HA keeps these about 10 days), or
    hourly rows (kept indefinitely) when no 5-minute rows exist for the span.
    Returns CSV lines without the header."""
    rows = []
    for table, period in (("statistics_short_term", "5min"), ("statistics", "hour")):
        sql = (f"select datetime(s.start_ts,'unixepoch','localtime'),'{period}',"
               f"round(s.mean,2),round(s.min,2),round(s.max,2) from {table} s "
               f"join statistics_meta m on m.id=s.metadata_id "
               f"where m.statistic_id='{TEMP_SENSOR}' "
               f"and s.start_ts >= strftime('%s','{start:%Y-%m-%d %H:%M:%S}','utc') "
               f"and s.start_ts <= strftime('%s','{end:%Y-%m-%d %H:%M:%S}','utc') "
               f"order by s.start_ts")
        r = ssh(f'sudo sqlite3 -readonly -csv /config/home-assistant_v2.db "{sql}"')
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200])
        rows = [ln.replace('"', "") for ln in r.stdout.splitlines() if ln.strip()]
        if rows:
            break
    return rows


def save_temperature(dest, start, end):
    """Merge the pantry temperature for start..end into dest (CSV, one row per
    statistics period), keeping rows HA may have purged since an earlier pull."""
    have = {}
    if dest.exists():
        for ln in dest.read_text().splitlines()[1:]:
            have[ln.split(",")[0]] = ln
    for ln in pull_temperature(start, end):
        have[ln.split(",")[0]] = ln
    dest.write_text("\n".join([TEMP_HEADER] + [have[k] for k in sorted(have)]) + "\n")
    return len(have)


def archive_session():
    """Keep a copy of the session's frames and state in photos/watch_<first frame>
    (gitignored) before the cache is cleared, as test data for the detector."""
    files = sorted((CACHE / "frames").glob("2*.jpg"))
    if not files:
        return
    dest = HERE.parent / "photos" / f"watch_{files[0].stem}"
    dest.mkdir(parents=True, exist_ok=True)
    new = [f for f in files if not (dest / f.name).exists()]   # tops up an earlier copy
    for f in new:
        shutil.copy2(f, dest)
    for extra in ("state.json", "chart.png", "temperature.csv"):
        if (CACHE / extra).exists():
            shutil.copy2(CACHE / extra, dest)
    print(f"saved {len(new)} new frames to {dest} ({len(files)} in the session)")


def run_once(dry, forced_jar):
    r = ssh(f"test -d {REMOTE} && {{ echo yes; ls {REMOTE}; }} || echo no")
    if r.returncode != 0:
        desktop_error(f"cannot reach the HA machine over ssh: {r.stderr.strip()[:200]}")
        return 1
    state_file = CACHE / "state.json"
    head, *remote_files = r.stdout.split()
    if head != "yes":
        if state_file.exists() or (CACHE / "frames").exists():
            archive_session()
            shutil.rmtree(CACHE)
            print("watch mode is off; cache cleared")
        return 0
    frames = CACHE / "frames"
    # a quick off/on between runs never shows the watcher "off": the new session has
    # no frame the old one had, so start over instead of mixing the two
    if any(f.name not in remote_files for f in frames.glob("2*.jpg")):
        archive_session()
        shutil.rmtree(CACHE)
        print("watch mode was restarted; cache cleared")
    frames.mkdir(parents=True, exist_ok=True)
    pull = subprocess.run(["rsync", "-a", "--include=2*.jpg", "--exclude=*",
                           f"{HOST}:{REMOTE}/", f"{frames}/"], capture_output=True, text=True)
    if pull.returncode != 0:
        desktop_error(f"could not pull frames from the HA machine: {pull.stderr.strip()[:200]}")
        return 1
    sess = Session(json.loads(state_file.read_text()) if state_file.exists() else None)
    files = sorted(frames.glob("2*.jpg"))
    if files and not dry:   # pantry temperature for the session, kept next to the frames
        try:
            save_temperature(CACHE / "temperature.csv", frame_time(files[0]) - timedelta(minutes=30),
                             datetime.now())
        except Exception as e:  # noqa: BLE001 - never blocks the alerts
            print(f"temperature not saved: {type(e).__name__}: {e}", file=sys.stderr)
    events = step(sess, files, forced_jar)
    failed = False
    for key, title, message in events:
        if post(title, message, dry):
            sess.sent.append(key)
        else:
            failed = True       # not recorded as sent, so the next run tries again
    if not dry:             # a dry run must not mark alerts as sent or move the jar state
        state_file.write_text(json.dumps(sess.dump()))
    print(f"{len(files)} frames, jar={sess.jar}, sent={sess.sent}, bumps={sess.bumps}")
    try:
        png = chart(sess, CACHE / "chart.png")
        if not dry:
            upload_chart(png)
    except Exception as e:  # noqa: BLE001 - the chart must never stop the alerts
        print(f"chart failed: {type(e).__name__}: {e}", file=sys.stderr)
    if failed:
        desktop_error("an alert could not be delivered to Home Assistant (webhook failed); will retry")
        return 1
    # heartbeat: HA texts Kris if this stops arriving while watch mode is on
    if not dry and not webhook({"heartbeat": True}):
        desktop_error("could not reach the Home Assistant webhook")
        return 1
    if (CACHE / "last_error.json").exists():
        (CACHE / "last_error.json").unlink()
    return 0


def replay(folder, forced_jar, every, chart_out=None):
    files = sorted(Path(folder).glob("2*.jpg"))[::every]
    sess = Session()
    t0 = frame_time(files[0])
    for n in range(1, len(files) + 1):
        for key, _title, message in step(sess, files[:n], forced_jar):
            mins = (frame_time(files[n - 1]) - t0).total_seconds() / 60.0
            print(f"{files[n - 1].stem}  (+{mins / 60:.1f} h)  {key}: {message}")
            sess.sent.append(key)
    print(f"jar={sess.jar} frames={len(files)} sent={sess.sent} bumps={sess.bumps}")
    if chart_out:
        print(f"chart: {chart(sess, Path(chart_out))}")


def main(argv):
    forced = None
    if "--jar" in argv:
        a, b = argv[argv.index("--jar") + 1].split("-")
        forced = (int(a), int(b))
    if "--save-temps" in argv:
        # backfill an archived session: --save-temps photos/watch_<first frame>
        d = Path(argv[argv.index("--save-temps") + 1])
        fs = sorted(d.glob("2*.jpg"))
        n = save_temperature(d / "temperature.csv", frame_time(fs[0]) - timedelta(minutes=30),
                             frame_time(fs[-1]) + timedelta(minutes=30))
        print(f"{n} temperature rows in {d / 'temperature.csv'}")
        return 0
    if "--replay" in argv:
        every = int(argv[argv.index("--every") + 1]) if "--every" in argv else 1
        out = argv[argv.index("--chart") + 1] if "--chart" in argv else None
        return replay(argv[argv.index("--replay") + 1], forced, every, out)
    return run_once("--dry-run" in argv, forced)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001 - last resort: say so rather than die silently
        if "--replay" not in sys.argv:
            desktop_error(f"watcher crashed: {type(e).__name__}: {e}")
        raise
