> Moved from `ha-repo/starter/` on 2026-11-07. Paths below are the new layout: scripts in `tools/`, photos in `photos/`, per-run outputs in `results/`, feeds in `data/feeds.csv`.

# Sourdough timelapse notes

How the pieces fit (moved off the dashboard):

- **Photos** are taken by `script.starter_timelapse_capture` every 30 minutes
  while `input_boolean.starter_timelapse_active` is on. They are saved on the HA
  machine as `/media/starter/<run>/YYYYMMDD_HHMM.jpg`, where `<run>` is the value
  of `input_text.starter_run` at the time. A second copy is written to
  `/media/starter/latest.jpg` for the dashboard's "Latest frame" card.
- **Pulling a run to this machine:** `tools/sync.sh <run>` copies it into
  `photos/<run>/` (gitignored). With no argument it lists the run folders
  on the HA machine. Deleting files under `/media/starter/` on the HA machine
  needs `sudo` (the SSH user can't).
- **Temperature:** `sensor.starter_pantry_temperature` is the tip of the Meater
  probe in the water jar; `sensor.starter_pantry_air_temperature` is the handle
  reading minus `input_number.starter_air_offset`. The probe is picked
  automatically by `sensor.starter_probe_in_use`.
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

- **Use:** flip `input_boolean.starter_watch` on in HA with the jar in view of the
  pantry camera. HA sets the run name to `watch`, turns on the timelapse and saves
  frames to `/media/starter/watch/`. Flip it off when done: the timelapse stops and
  the frames are deleted. It refuses to start while the experiment timelapse
  (`starter_timelapse_active`) is on. Switching off also clears
  `input_text.starter_run`, so set a run name again before the next experiment.
- **Watcher:** `tools/watch_service.py`, run by a systemd user timer at :02 and :32
  past each hour (just after each frame). Nothing runs between frames. It checks
  whether `/media/starter/watch` exists on the HA machine, pulls new frames into
  `~/.cache/starter-watch/`, finds the jar by shape (matches `tools/jar_template.png`, the rim and
  upper glass of the Weck jar, so it works before anything has moved), tracks the dough
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
