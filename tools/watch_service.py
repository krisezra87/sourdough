#!/usr/bin/env python3
"""Watch mode: tell Kris when a starter or levain has peaked, from the pantry timelapse.

Run on a timer (starter-watch.timer (installed by tools/install-watch.sh)), once just after each frame. Each run:
  1. asks the HA machine whether watch mode is on (the folder /media/starter/watch
     exists only while input_boolean.starter_watch is on; HA deletes it when it goes off)
  2. pulls any new frames into ~/.cache/starter-watch/
  3. finds the Weck jar by shape (tools/jar_template.png), tracks the dough height, and
     works from the rate of change, so it needs no feed time and can start mid-rise
  4. sends at most one "nearly there" and one "peaked" phone notification per session
     through the HA webhook whose URL is in tools/watch_secret (gitignored), and a
     heartbeat after every good run; HA texts Kris if the heartbeat stops
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
"""
import json, shutil, subprocess, sys, urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_heights import colourfulness, measure_jar  # noqa: E402

HERE = Path(__file__).resolve().parent
HOST, REMOTE = "ha", "/media/starter/watch"
CACHE = Path.home() / ".cache" / "starter-watch"
SECRET = HERE / "watch_secret"

ROWS = (1500, 2000)             # band of the frame that contains the jars
SEARCH = (800, 3500)            # columns to search for the jar
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


def median3(v):
    out = list(v)
    for i in range(1, len(v) - 1):
        out[i] = float(np.median(v[i - 1:i + 2]))
    return out


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


def decide(ts, heights, sent):
    """ts in minutes, heights in px. Returns a list of (key, title, message)."""
    keep = [i for i, t in enumerate(ts) if t - ts[0] >= SETTLE_MIN]
    ts, heights = [ts[i] for i in keep], [heights[i] for i in keep]
    if len(heights) < 4:
        return []
    ts = [t - ts[0] + SETTLE_MIN for t in ts]
    sm = median3(limit_steps(heights))
    top, low = max(sm), min(sm)
    rise = (top - low) / low
    slopes = rolling_slopes(ts, sm)
    known = [s for s in slopes if s is not None]
    events = []
    hrs = (ts[-1] - ts[0]) / 60.0

    if rise < RISE_MIN:
        return events

    i_top = sm.index(top)
    # two points in a row below the top, and enough history, so one noisy frame
    # or a bumped camera early on can't call a peak
    peaked = (len(sm) >= 6 and hrs >= 2 and i_top <= len(sm) - 3
              and all(y <= top * (1 - PEAK_DROP) for y in sm[-2:]))
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

    def dump(self):
        return {"jar": self.jar, "meas": self.meas,
                "sent": self.sent, "skipped": self.skipped}


def step(sess, files, forced_jar=None):
    """Process the frames seen so far; returns events to send. Mutates sess."""
    colour = [f for f in files if f.stem not in sess.skipped]

    if sess.jar is None:
        if forced_jar:
            sess.jar = list(forced_jar)
        elif colour:
            a = load(colour[-1])
            if colourfulness(a) < 3:        # night / infrared frame: shape match is unreliable
                sess.skipped.append(colour[-1].stem)
                return []
            band = locate(a)
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
    for f in colour:
        if f.stem in sess.meas:
            continue
        a = load(f)
        if colourfulness(a) < 3:
            sess.skipped.append(f.stem)
            continue
        try:
            s, b = measure_jar(a, x0, x1, *ROWS)
        except ValueError:      # no warm pixels in the box at all
            sess.skipped.append(f.stem)
            continue
        sess.meas[f.stem] = [int(s), int(b)]

    stems = [f.stem for f in colour if f.stem in sess.meas]
    if not stems:
        return []
    bot = float(np.median([sess.meas[s][1] for s in stems]))
    heights = [bot - sess.meas[s][0] for s in stems]
    t0 = frame_time(Path(stems[0] + ".jpg"))
    ts = [(frame_time(Path(s + ".jpg")) - t0).total_seconds() / 60.0 for s in stems]
    return [e for e in decide(ts, heights, set(sess.sent)) if e[0] not in sess.sent]


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


def archive_session():
    """Keep a copy of the session's frames and state in photos/watch_<first frame>
    (gitignored) before the cache is cleared, as test data for the detector."""
    files = sorted((CACHE / "frames").glob("2*.jpg"))
    if not files:
        return
    dest = HERE.parent / "photos" / f"watch_{files[0].stem}"
    if dest.exists():
        return
    dest.mkdir(parents=True)
    for f in files:
        shutil.copy2(f, dest)
    if (CACHE / "state.json").exists():
        shutil.copy2(CACHE / "state.json", dest)
    print(f"saved {len(files)} frames to {dest}")


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
    events = step(sess, files, forced_jar)
    failed = False
    for key, title, message in events:
        if post(title, message, dry):
            sess.sent.append(key)
        else:
            failed = True       # not recorded as sent, so the next run tries again
    if not dry:             # a dry run must not mark alerts as sent or move the jar state
        state_file.write_text(json.dumps(sess.dump()))
    print(f"{len(files)} frames, jar={sess.jar}, sent={sess.sent}")
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


def replay(folder, forced_jar, every):
    files = sorted(Path(folder).glob("2*.jpg"))[::every]
    sess = Session()
    t0 = frame_time(files[0])
    for n in range(1, len(files) + 1):
        for key, _title, message in step(sess, files[:n], forced_jar):
            mins = (frame_time(files[n - 1]) - t0).total_seconds() / 60.0
            print(f"{files[n - 1].stem}  (+{mins / 60:.1f} h)  {key}: {message}")
            sess.sent.append(key)
    print(f"jar={sess.jar} frames={len(files)} sent={sess.sent}")


def main(argv):
    forced = None
    if "--jar" in argv:
        a, b = argv[argv.index("--jar") + 1].split("-")
        forced = (int(a), int(b))
    if "--replay" in argv:
        every = int(argv[argv.index("--every") + 1]) if "--every" in argv else 1
        return replay(argv[argv.index("--replay") + 1], forced, every)
    return run_once("--dry-run" in argv, forced)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001 - last resort: say so rather than die silently
        if "--replay" not in sys.argv:
            desktop_error(f"watcher crashed: {type(e).__name__}: {e}")
        raise
