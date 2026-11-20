# Sourdough repo: notes for Claude

Starter routine, feed log and analysis. The Home Assistant side (pantry camera, watch mode, temperature sensors, the "Starter" dashboard) lives in `~/GIT/ha-repo`; its `CLAUDE.md` and memory cover HA work.

## Current direction (2026-11-12)
- The multi-jar experiments are over. One whole wheat mother lives in the fridge and is built into the levain the night before a bake. The schedule is `docs/starter_schedule.tex` (amounts are macros at the top; build with `latexmk -pdf` in `docs/`, build files are gitignored). The direction note is at the top of `experiments.md`.
- Each build is observed with HA watch mode (`input_boolean.starter_watch`), not a new experiment run. The watcher archives the frames to `photos/watch_<first frame>/`.

## Logging
- Flour: unless the user says otherwise, a feed uses King Arthur whole wheat (`flour_class` `whole_wheat`); log it as that rather than leaving it blank.
- One row per feed in `data/feeds.csv` (use run_id `routine` for routine builds). Record weights and times as the user states them; blank, never guessed. Conventions are in `README.md`.
- Ready times come from the frames, read by eye from crops; never from the detector CSV alone.

## Working rules
- The user commits; leave changes unstaged unless asked. Never `git push` or `git pull`.
- HA changes: edit `~/GIT/ha-repo` YAML, never the HA MCP write tools. On the HA Pi (`ssh ha`), only delete named files in `/media/starter/`.
- Writing: plain and short, engineering style. Units always; numbers over adjectives. Give less text and leave room for follow-up questions on direction.

## Height model data (collecting since 2026-11-20)
- Watch sessions on the ESP32 rig (1600x1200 frames in `photos/watch_*/`) are training data for a small height model. Target before training: about 300 frames over 6 or more sessions, with varied fill levels and lighting (the rig gets moved around the pantry on purpose). When starter work comes up, count them and tell the user once the count is close.
- Environment for training: uv with `pyproject.toml` (CPU-only torch in an `ml` group), set up at training time.
