> Moved from `ha-repo/starter/` on 2026-11-07. Paths below are the new layout: scripts in `tools/`, photos in `photos/`, per-run outputs in `results/`, feeds in `data/feeds.csv`.

# Sourdough timelapse notes

How the pieces fit (moved off the dashboard):

- **Photos** are taken by `script.starter_timelapse_capture` every 30 minutes
  while `input_boolean.starter_watch` is on, from the starter rig's ESP32-CAM
  (`camera.pantry_pantry_cam_camera`). They are saved on the HA machine as
  `/media/starter/watch/YYYYMMDD_HHMM.jpg`, and every shot also writes
  `/media/starter/latest.jpg` for the dashboard's "Latest frame" card. Until
  2026-11-19 experiment runs used a Reolink camera, an experiment timelapse switch
  and a run name (`/media/starter/<run>/`); those helpers are gone, but the old
  run folders remain.
- **Pulling a run to this machine:** `tools/sync.sh <run>` copies it into
  `photos/<run>/` (gitignored). With no argument it lists the run folders
  on the HA machine. Deleting files under `/media/starter/` on the HA machine
  needs `sudo` (the SSH user can't).
- **Temperature:** `sensor.pantry_temperature_sensor_temperature` and
  `sensor.pantry_temperature_sensor_humidity` (Zigbee sensor in the pantry, air
  only). Before 2026-11-16 a Meater probe in a water jar fed
  `sensor.starter_pantry_temperature` / `sensor.starter_pantry_air_temperature`;
  those entities are gone.
- **Feed log:** `data/feeds.csv`. **Measured results:** `results/`.
- **Dashboard:** "Starter" in the HA sidebar (`dashboards/starter.yaml`). Past-run
  summaries come from two scripts. `tools/measure_heights.py <run> --jar N:x0-x1 ...
  [--qa]` measures the dough in every frame of `photos/<run>/` and writes
  `results/<run>_height.csv` (`--qa` also writes a contact sheet with the detected
  surface drawn on, to check by eye). `tools/summarize_run.py <run> --title "..."`
  reads that CSV and the run's rows in `data/feeds.csv`, writes `<run>_summary.json`
  and the chart in `www/starter/`, and prints the cards to paste into the
  dashboard. Metric definitions are in the scripts' docstrings. Jar columns for Run 0:
  `--jar 1:1820-1990 --jar 2:2250-2420 --jar 3:2680-2850`.
- **Experiment plan:** `experiments.md`.

## Watch mode (levain / revival, not experiments)

A ballpark "has it peaked?" helper for making levain or reviving a starter, using
rate of change so it can be started at any point in the rise.

- **Use:** flip `input_boolean.starter_watch` on in HA with the jar in the rig.
  HA takes a frame right away, then every 30 minutes, into `/media/starter/watch/`.
  Flip it off when done: the frames are deleted (the watcher archives its copy).
- **Watcher:** `tools/watch_service.py`, run by a systemd user timer at :02 and :32
  past each hour (just after each frame). Nothing runs between frames. It checks
  whether `/media/starter/watch` exists on the HA machine, pulls new frames into
  `~/.cache/starter-watch/`, finds the jar (rig frames: fixed columns, since the jar
  sits in the nest; old Reolink frames, told apart by width: by shape, matching
  `tools/jar_template.png`), tracks the dough
  height and posts to the HA webhook. The first 45 minutes of frames are ignored.
  If a quick off/on between runs leaves the cache holding frames HA no longer has, it
  clears the cache and starts a fresh session.
- **Alerts** (each at most once per session): "nearly there" when the rise has slowed
  to 25% of its fastest (and is 8%+ up); "peaked" when the last two smoothed heights
  are 2% below the maximum (needs 2 h+ of frames, so it lands late on a flat plateau).
  A single-frame jump of more than 10% is capped (the detector can catch smear on the glass),
  and "nearly there" has to hold for 3 frames in a row.
  After 6 h without finding a jar it says so once. If the camera is moved, retake the
  template: crop the jar's rim and upper glass (about 360 x 180 px at full resolution) to
  `tools/jar_template.png`.
- **Install / re-install** (new computer, moved repo): `tools/install-watch.sh`
  (`--uninstall` to remove). It checks dependencies, rebuilds the gitignored
  `tools/watch_secret` webhook URL from the id in `automations.yaml` ("Starter watch -
  notify"; set `HA_URL` if HA isn't at 192.168.1.50:8123), writes the systemd units and
  enables the timer. The timer only fires while you are logged in.
- **Try it on saved frames:** `tools/watch_service.py --replay photos/<run>
  [--jar x0-x1] [--every N]` prints when each alert would have fired; `--dry-run`
  does a live check without sending or saving state.
- **If the watcher fails:** errors (ssh, rsync, webhook, crash) pop up in dunst via
  `notify-send`. The watcher also posts a heartbeat after every good run; if none
  arrives for 75 minutes while the switch is on, HA texts you ("Starter watch -
  watcher stopped checking in"), which covers the machine being off or asleep.
- **Known limits:** the jar finder only knows the Weck jar; any other jar needs
  `--jar x0-x1` or a new template. The match score can't tell a jar on a new background
  from an empty counter, so a missing jar shows up as flat or noisy heights and no alerts
  rather than a "can't find the jar" message. Alerts need a few hours of frames. On past runs "nearly there" came 2 to 6 h
  before the measured "ready" time for slow jars, so treat it as a prompt to go look.

### Robustness, chart and forecast (added 2026-11-19/20)

- **Noise gate:** no alert unless the smoothed rise is at least 5x the frame-to-frame
  noise. Noise = each raw height against the mean of its two neighbours (a steady rise
  cancels out), robust sigma via the median. Real archived runs score 30-215x; the first
  rig session (2026-11-19) scored 0.2x and sent a false "peaked" before this existed.
- **Bump detection (rig only):** the jar glass above the dough (rows 20-280) and the
  nest collar (rows 1080-1200) are compared with the previous measured frame. About
  0.99 similarity when untouched, about 0.7 after the jar was moved; below 0.93 in both
  starts a new segment. Each segment gets its own bottom and is shifted to continue
  from the last height before the bump. Shown on the chart as "jar moved".
- **Chart:** redrawn after every run to `~/.cache/starter-watch/chart.png` and copied
  to HA `/config/www/starter/live/watch.png` (gitignored in ha-repo; the folder is owned
  by `hassio` so the watcher can write it). Starter dashboard, "Height" card. Dots =
  each frame, blue line = smoothed height, blue band = +/- frame noise, dotted lines =
  top time and total rise once the rise is clear. `--replay DIR --chart OUT.png` draws
  one for a saved session.
- **Forecast (feed-agnostic):** nothing is entered per feed. The session start (watch
  turned on) stands in for the feed time. The rise is modelled as a logistic curve,
  h(t) = b * (1 + R * S((t - t_half) / w)), which is what logistic growth of the culture
  gives. Ready (90% of the rise) = t_half + 2.2 w.
  - Prior (what it believes before the rise shows), from the 10 completed jars in
    `results/*_summary.json`: half rise median 6.9 h after the feed, w median 1.35 h,
    rise R median 0.5 (1.5x), all log-normal and widened for fridge starters.
  - Update: a grid of about 41,000 candidate curves (t_half 1-24 h, w 0.5-4 h,
    R 0.08-2.0). Each frame reweights every candidate by how well it fits; b is solved
    exactly per candidate. The chart shows the median curve (dashed orange), the 80%
    band, and the 10-90% ready window.
  - Backtest on the 7 Reolink watch sessions, checkpoints every 1.5 h up to the peak:
    the true ready time fell inside the 80% range 23 of 32 times; median error 1.1 h.

#### Why Student-t instead of Gaussian (to read later)

This is the Student-t *distribution* used as the error model, not a Student's t-test.
The forecast scores each candidate curve by how far each frame sits from it, in units
of the noise sigma (call that r). The error model decides how much a miss costs:

| Frame off by | Gaussian cost r^2/2 | Student-t (nu = 3) cost 2 ln(1 + r^2/3) |
|---|---|---|
| 1 sigma | 0.5 | 0.58 |
| 3 sigma | 4.5 | 2.77 |
| 5 sigma | 12.5 | 4.47 |
| 10 sigma | 50 | 7.07 |

Ordinary frames cost about the same either way. A detector jump (a frame 10 sigma off)
costs 50 under the Gaussian, as much as a hundred good frames fitting slightly worse,
so one bad frame can drag the whole fit. Under Student-t it costs about 7, so the curve
follows the run of good frames. nu sets how heavy the tails are; nu -> infinity is the
Gaussian. Settings chosen by backtest (80% range coverage out of 32 checkpoints):

| Noise floor | Gaussian | Student-t nu=3 |
|---|---|---|
| 2% of height | 18 | 21 |
| 4% of height | 23 | **23 (used)** |
| 6% of height | 23 | 22 |

The noise floor matters more than the tails on these runs: a fit that trusts the
frames to better than 4% of the height is overconfident, because the logistic shape
is itself only approximate. Student-t was kept for the jumpy rig readings.

#### Not built yet

- **Temperature term.** The pantry has a temperature sensor
  (`sensor.pantry_temperature_sensor_temperature`). The toaster oven and the composter
  warm the pantry when they run, which should speed the rise. Plan: run the logistic on
  "warm time" instead of clock time, tau = integral of 2^((T(t) - T_ref) / dT) dt (the
  growth rate doubles every dT; a common rule of thumb is about 18F), fit dT across
  sessions once some have clearly different temperatures. The data is already being
  collected (see "Temperature data" below).

#### Temperature data (collected since 2026-11-20)

Every watcher run reads the pantry sensor's 5-minute statistics for the session (from
30 min before the first frame) out of HA's recorder database, read-only
(`ssh ha sudo sqlite3 -readonly`), and merges them into
`~/.cache/starter-watch/temperature.csv` (`time_local,period,mean_f,min_f,max_f`).
Rows already saved are kept, so HA purging old data doesn't lose any. The archive copies
the file into `photos/watch_<first frame>/` with the frames. HA keeps 5-minute
statistics about 10 days and hourly statistics indefinitely; for an older session,
`tools/watch_service.py --save-temps photos/watch_<first frame>` falls back to hourly
rows (`period` = `hour`). The sensor went in on 2026-11-16, so sessions before that
have no temperature.
- **Better height measurement:** read the level through the nest collar's window, then
  a learned model (row profiles, then a small CNN) once about 300 rig frames over 6+
  sessions are archived. See CLAUDE.md, "Height model data".
- Dropped by choice: a "ready around X" phone notification (the chart is enough).
