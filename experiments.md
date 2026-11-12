> Moved from `ha-repo/starter/` on 2026-11-07. Paths below are the new layout: scripts in `tools/`, photos in `photos/`, per-run outputs in `results/`, feeds in `data/feeds.csv`.

# Sourdough starter experiments (Bonne Maman jar version)

## Why we're doing this

- Cut discard (currently about 1.5 cups per day).
- Move to one feeding per day, or fewer with the fridge.
- Know the peak time for each routine so it lands while awake.
- Find out whether a flour blend suits better than 100% whole wheat.
- Make sure the starter survives the 2-week trip.

Starting point (baseline): about 80g starter + 100g whole wheat + 100g water at ~71F house temperature (pantry may be warmer), fed at 9:45 AM, ripe by roughly 8 PM (about 10 h).

Edit these parameters before starting:

```
FEED_TIME = 21:45          # once-daily feed time for test jars
AWAKE_WINDOW = 07:00-21:00 # peak should land inside this
SAMPLE_EVERY = 30 min
```

---

## Current status (updated 2026-10-13, written so a fresh session can pick up)

**Run 1 (ratio axis, run name `run1_starter_amt`, pint jars) finished 2026-10-14 13:30; results are below.** Setup: Left to right, left closest to the wall. Same starter as the Run 0 pint jars, whole wheat (King Arthur), 100% hydration, lids on:

| Jar | Starter : flour : water | Fed |
|---|---|---|
| 1 (left, Control) | 30 : 36 : 36 | 2026-10-13 12:18 |
| 2 (middle, A) | 16 : 40 : 40 | 2026-10-13 12:21 |
| 3 (right) | 4 : 40 : 40 | 2026-10-13 12:26 |

- One long cycle of about 25 h with no second feed, so the jars also show behaviour past peak. The starter was not reused. The timelapse helper was turned off 2026-10-14 13:35.

**Run 1 results (time from each jar's feed; all numbers from smoothed series):**

| Jar | Starter : flour : water | Ready (90% of rise) | 80% of rise | Peak | Half rise | Lag | Rise ratio | Plateau |
|---|---|---|---|---|---|---|---|---|
| 1 | 30 : 36 : 36 | 9 h 00 min | 7 h 55 min | 12 h 40 min | 6 h 30 min | 2 h 35 min | ~2.1x* | 4 h, then fell to ~1.9x by the end |
| 2 | 16 : 40 : 40 | 11 h 15 min | 10 h 20 min | 19 h 40 min | 7 h 10 min | 4 h 40 min | 1.28x | 13 h+ (still flat at the end) |
| 3 | 4 : 40 : 40 | 15 h 55 min | 14 h 10 min | 18 h 35 min | 10 h 25 min | 7 h 10 min | 1.31x | 7 h 30 min+ (still flat at the end) |

\* Jar 1 was measured by brightness (`--lum 1`) because its glass was smeared with dough-coloured residue; its start height is uncertain by about 15-20 px of a ~70 px column, so its true rise ratio is roughly 1.8-2.1x. Jars 2 and 3 used the colour method; the brightness method gave inflated ratios for them (start surface placed too low), so it was not used. The 90% times are less sensitive to this than the ratios, but not immune.

- **Ready time vs dilution is close to a straight line in ln(total / starter):** ln = 1.22 (jar 1), 1.79 (jar 2), 3.04 (jar 3) gives 9.0, 11.25 and 15.9 h, a slope of about 3.7-3.9 h per ln unit and an intercept of about 4.4 h (`t90 ~ 4.4 + 3.8 * ln(total/starter)` hours at about 68-69 F). The pint Run 0 replicates (ln 1.2, 8.6-9.1 h) land on the same line. The Weck jar test (ln 1.30, 6.9 h) is about 2.4 h earlier than the line, so run-to-run or jar/starter state differences are still the main unexplained error.
- **Practical reading:** 30 g carryover is ready about 9 h after feeding, but is past its plateau by ~15 h. 16 g carryover (A) is ready at ~11 h 15 min and stays flat for 13 h+, which is the more forgiving once-a-day option. 4 g is slow (16 h) and its carryover is too uncertain to trust.
- **Data gaps:** frames missing at 19:00, 01:30 and 03:00; 12:29, 12:31 (camera moved) and 13:30 on Oct 14 (glare glitch) were excluded; the live probe died about 08:28 on Oct 14, so the temperature series ends there.
- Feed log rows are in `data/feeds.csv`; photos in `/media/starter/run1_starter_amt/` (sync with `tools/sync.sh run1_starter_amt`).
- Camera was bumped while setting up: frames 20261013_1229 and 20261013_1231 are in a different position. Skip them (`--skip 20261013_1229 --skip 20261013_1231`); time-zero is the 12:35 frame. The stray 12:29 frame is also in `/media/starter/run0_pint/` on the Pi until someone runs `sudo mv` on it.
- Jar bands for `measure_heights.py` (full-res columns): `--jar 1:1650-1880 --jar 2:2040-2260 --jar 3:2400-2610`, rows 1550-1950; look at a QA sheet (`--qa`) before trusting numbers.
- Temperature probes: two Meaters, one charged and in the water jar, the other charging; expect to swap them. The sensors auto-pick whichever probe reports (sticky), so a swap shows as a short gap and a new ID in `sensor.starter_probe_in_use`.
- Rough pre-run guess (exponential growth scaled from the pint Control jar, ignores lag): jar 1 ready around 21:00, jar 2 around 01:00, jar 3 around 10:00 on Oct 14, possibly later.

**Decisions made so far**
- **Headline metric is "ready" = time to 90% of the total rise** (interpolated, from the smoothed series). It is far more repeatable than the peak (pint run: jar-to-jar spread about 15 min vs about 75 min). Peak, half rise, lag and plateau are secondary. The 80% crossing is kept in the JSON as a cross-check.
- The three Bonne Maman jars of Run 0 are not used: uncovered jars, scale off. Their data is in `results/run0_bonne_maman_*` but it is excluded from the dashboard and the results log.
- Tolerance: about +/- 2 h on ready time is acceptable, because the usable window is about 3 h.
- Weck jar test (Oct 7-8) is its own run; it is not part of the numbered plan.
- **Minimum practical carryover is about 15 g of starter.** The jars are not cleaned each time and some always sticks to the sides, so carryovers below that carry too much relative error. Jar 3 of Run 1 (4 g) is kept on purpose as the extreme end of the dilution range: it gives the fit its leverage and shows where the simple model breaks, but its carryover is uncertain by a large fraction (a couple of grams of smear is half the dose), so it is weighted accordingly and not treated as a candidate routine. The old pint-table rows B (8 g) and C (4 g) are therefore not candidates; if a lower carryover than A is wanted, use a larger total feed (observed rises are only 1.3-1.5x, so the 1/4-capacity headroom rule is conservative) rather than a smaller starter.
- Going forward the starter is fed in Weck jars, not pint jars (pint headroom rules above are moot for the routine; they only apply to the experiments in pint jars).
- **Idea (not done): etch each Weck jar's empty weight into the glass** (glass-etching cream or engraving pen) so the tare survives the dishwasher and gross-weight dosing needs no label.
- Better way to set the carryover: the two Weck jars weigh about 399 g (+/- 2 g) empty, so weigh the jar with the starter in it and leave the target gross weight (tare + carryover) instead of spooning an amount out. The residue on the sides then counts toward the weighed carryover.

**Next steps**
1. Run 1 is done and written up (card and results log). Decide the ratio for Run 2: Control (30 g) is ready at 9 h but has a short plateau; A (16 g) is ready at 11 h 15 min with a 13 h+ plateau. Leaning A.
2. Run 2 (flour axis) was planned to start the evening of Oct 14 but no starter was fed (the user was ill), so it is postponed; it starts when a starter is ready. Feed the Weck jar starter about 7.5 h before the start (it reached 90% in 6 h 55 min and peaked at 8 h 10 min in the Weck jar test, and was usable for 3 h+), so a 7 PM start means feeding around 11:30 AM and a 9:45 PM start around 2 PM. Three jars of the chosen ratio: 100% whole wheat, 50/50 whole wheat / all-purpose, 100% all-purpose; note the all-purpose brand.
**Schedule constraint:** the user leaves Friday 2026-10-16 for about two weeks, so only about two more experiment slots exist: Run 2 starting the evening of Wed Oct 14 (second daily feed Thu morning in the same jars), and possibly one overnight gap-filling set starting Thu evening. The starter needs its fridge protocol (Run 4 feed) before leaving. No fit script until there is enough data; for now the job is clean data logging.

**Temperature data caveat:** the two Meater probes are also the user's meat thermometers (a steak on the grill shows as a 141 F spike), so before any temperature is used, clip it to the run's own window (feed time to last frame) and to 60-80 F, and note gaps (charging, cooking). Do not use the daily statistics.

**Log for every feed (so the later fit is possible):** actual gross weights (starter, flour, water, as weighed), flour types, jar, time fed, how long since the starter's last feed and its state (peaked, past peak), lids on or off, and the pantry temperature (probe; note any gap).

3. After the ratio and flour are chosen: Run 3 (sitting past peak), Run 4 (fridge), Run 5 (bake), then 2-3 replicates of the winning recipe to tighten the numbers.

---

## Target model (the end goal of all the runs)

**Aim:** a ballpark equation, with error bars, from ABOUT four inputs to two outputs, so a feed can be planned without running a test:

- Inputs (grams): starter `s`, water `w`, whole wheat flour `fw`, all-purpose flour `fa`.
- Output 1: **time to 90% of the rise** ("use time", the `ready_90_min` number from `summarize_run.py`).
- Output 2: **the amount of starter produced**, which is just the sum of the inputs (minus a little gas and evaporation); it is bookkeeping for propagating the starter, not something to fit.

**Shape of the model (a starting hypothesis, to be tested with the data):** growth is roughly exponential, so ready time is a lag plus a growth time proportional to the log of the dilution:

    t90 = a + b * ln(total / s) + c * phi + d * (h - 1) + e * (T - 71)

with `total = s + w + fw + fa`, `phi` the whole wheat fraction of all flour (counting the starter as half flour and half water, whole wheat), `h` the hydration (water / flour, same counting), and `T` the mean pantry temperature in F from the probe. Only three ratios matter (dilution, whole wheat fraction, hydration); the absolute amounts only matter for the jar, not the time. Start with `a` and `b` for whole wheat only, then see how much `c` and `d` move it.

**What we know so far:** within a run the jar-to-jar spread of the ready time is small (about 15 min, pint run), but two runs at nearly the same dilution disagree by over an hour and a half (pint Run 0: 8 h 35-9 h 05 at s/total = 0.30; Weck test: 6 h 55 at 0.27). So the between-run difference, not the jar noise, is probably the main error. Likely hidden variables: how ripe or old the starter was when it was used, temperature, jar size, and the weighing accuracy. Log the starter's age/state at each feed, the actual gross weights, and the temperature.

**Data needed:** each jar is one point. For a 3 to 4 parameter fit plus a run-to-run effect, aim for roughly 15-25 jars across at least 5 different days, spanning dilution (4 g to 30 g starter in the same total), hydration and whole wheat fraction, with the winning recipe repeated 2-3 times. Fit by ordinary least squares on the log-dilution first; use bootstrap or prediction intervals for the error bars, and weight jars by how well their carryover is known (the 4 g jar is the least certain).

**Starter propagation:** the output mass is additive, so the question is only which starter to keep. Working recommendation (to decide after the runs): keep a small pure whole wheat starter as the reference and backup (fridge, fed weekly; the dried backup already exists), and take the working starter and the blends from it. The flour in the carryover is part of the model (`phi` counts it), so a whole wheat mother always adds a known whole wheat share to a blend.

---

## Jar sizing (read first)

Bonne Maman jars are small, so test feeds are small. Rules:

1. Measured: the jar holds 272g of water filled to the neck (the bottom of the threads), which is the usable limit. Call that CAPACITY (ml ~ g).
2. Keep the starting total (starter + flour + water) at or below about 1/4 of CAPACITY, i.e. about 68g. Whole wheat at 100% hydration can rise 2-3x or more, and it needs headroom.
3. If the starter reaches the jar shoulder during a run, reduce the total next time and note it.
4. Use a scale that reads 1g or better. Carryovers of 3-5g are error-prone on a 1g scale; a 0.1g scale is ideal.
5. All jars in a run must be identical, filled the same way, in fixed positions.

Test feeds (all 100% hydration, flour = water):

| Label | Starter : flour : water | Grams | Total |
|---|---|---|---|
| Control (about the current ratio) | 1 : 1.2 : 1.2 | 20 : 24 : 24 | 68g |
| A | 1 : 2.5 : 2.5 | 10 : 25 : 25 | 60g |
| B | 1 : 5 : 5 | 5 : 25 : 25 | 55g |
| C (optional; needs 0.1g scale, or use if B peaks too early) | 1 : 10 : 10 | 3 : 30 : 30 | 63g |

The jar capacity is already measured, so these numbers should be used as written.

### Pint jar version (provisional)

Moving the runs to pint jars. Same rules as above, scaled up; everything else (procedure, camera, analysis, runs, decision rules) is unchanged.

1. **CAPACITY = 400g (decided, not measured)**: the jars are labeled wide mouth pints, which hold about 473g of water brim-full; 400g is the usable fill to the neck (bottom of the threads). If a jar turns out to be unusual, set the total to 1/4 of the measured value and scale the grams proportionally.
2. Starting total at or below 1/4 of CAPACITY, i.e. about 100g.
3. The larger carryovers make a 1g scale adequate for everything except C.
4. Keep every jar in a run the same make and fill, and re-check camera framing: pint jars are taller, so the line of sight and the reference tape may need to move.

| Label | Starter : flour : water | Grams | Total |
|---|---|---|---|
| Control (about the current ratio) | 1 : 1.2 : 1.2 | 30 : 36 : 36 | 102g |
| A | 1 : 2.5 : 2.5 | 16 : 40 : 40 | 96g |
| B | 1 : 5 : 5 | 8 : 40 : 40 | 88g |
| C (optional; use if B peaks too early) | 1 : 10 : 10 | 4 : 40 : 40 | 84g |

**Practical floor:** B (8 g) and C (4 g) are below the ~15 g minimum carryover that can be handled reliably with uncleaned jars (see Current status), so they are not candidates as written. The 1/4-capacity headroom rule is also conservative: measured rises are only 1.3-1.5x.

Run 4 pre-fridge feed, scaled to the same ~1/4 rule: about 8g starter + 45g flour + 38g water (stiffer, flour-heavy), 1 hour at room temp, then fridge.

---

## Feeding and mixing procedure

- Feed all jars within about 10 minutes of each other at FEED_TIME, once every 24 h.
- Each day: stir, leave the carryover (or weigh the carryover into the jar), discard the rest, wipe the sides above the line, add flour then water, mix with a small spoon or chopstick, mark the starting level, and cover loosely.
- Give each condition 3 consecutive daily cycles. The first cycle shows the immediate response. Cycles 2-3 show the adapted behavior. Record the peak time for each cycle.
- Keep the main starter on its normal routine in parallel, so the experiment never puts the culture at risk. **Make a dried backup first** (thin layer on parchment, dry until brittle, store in a jar).

---

## Camera and Home Assistant setup

Camera: the spare Reolink Argus Eco Ultra, **not yet added to HA**. The Reolink battery-camera support in HA is new, and it isn't confirmed that this model exposes a snapshot entity. Test first.

Known entities:
- `light.pantry_lights` (pantry is closed and off the kitchen; the light may come on at any time)
- An existing automation `automation.pantry_light_on_motion` should not conflict with the new one: restore the light's previous state after each snapshot.
- No pantry temperature sensor was found. Consider adding one and logging it alongside the photos.

Steps for Claude Code:

1. Add the camera via the Reolink integration; enable its snapshot entity (disabled by default); confirm a snapshot works; measure how long the camera takes to wake.
2. Automation every 30 min: turn on the pantry light, wait ~15 s for camera wake, call `camera.snapshot` to `/media/starter/YYYYMMDD_HHMM.jpg`, restore the light state. Check that /media (or the chosen folder) is allowed for snapshots.
3. Check the camera battery after 24 h. If it drains quickly, power it continuously or reduce to hourly sampling outside the expected peak window.
4. Framing: jars in a fixed row (left to right A, B, C or Control, A, B), camera at roughly jar level so the surface line is visible, matte backdrop, label each jar with tape. Add a piece of tape somewhere fixed in the frame as a reference for camera shifts.
5. Take calibration shots first (see below).

Fallback if snapshots won't work: a phone on a stand with a time-lapse app or timed photos.

---

## Analysis (what "the peak" means)

For each jar in each cycle:

1. Measure the surface position (pixel row) in each photo, relative to the jar bottom and the starting-level mark.
2. Build height vs. time, with smoothing (e.g., a 3-point rolling median).
3. **Peak time** = time of the smoothed maximum, confirmed by at least 2-3 consecutive lower readings afterward.
4. Also record: time to reach 50% of the rise, the rise ratio (peak height / starting height), and how long the peak holds before falling.
5. Verify a few frames by eye per run. Bubbles, a flat or concave surface, and glare can confuse a simple measurement.
6. Output a CSV (jar, condition, cycle, peak time, rise ratio, hold time, notes) and a plot.

A fixed camera and fixed jars mean that "higher or lower than last picture" is meaningful without a ruler. A moved camera or jar breaks that, so watch the reference tape.

---

## Experiments

### Run 0: Calibration and replicates
**Why:** confirms the camera works, that small jars reproduce your known timing, and how much jar-to-jar noise to expect.
**Jars:** 3 identical jars, all Control feed (20 : 24 : 24), whole wheat.
**Check:** do all three peak within about 1 hour of each other, and near your known ~10 h? If not, fix the setup before continuing.

**Pint jar repeat of Run 0:** the first Run 0 was in Bonne Maman jars; the plan now repeats it in pint jars.
- **Jars:** 3 identical pint jars, same make, fixed left/middle/right positions.
- **Feed (each jar):** Control, 30g starter : 36g flour : 36g water (102g total), whole wheat (King Arthur), 100% hydration. Weigh water to the gram this time so all three get the same amount (the Bonne Maman run had 24 vs 25g).
- **Setup:** CAPACITY is taken as 400g (see Pint jar version); mark the starting level, and note the reference tape position after reframing. The dried backup is already made.
- **Cycles:** 3 consecutive daily cycles at FEED_TIME, as in the standard procedure.
- **Pass criteria:** all three peak within about 1 hour of each other, near ~10 h, with a rise ratio well above the 10% noise floor (the Bonne Maman run's 1.08-1.34x was marginal). Then move on to Run 1 with these jars.

### Run 1: Ratio axis (whole wheat)
**Status:** running as `run1_starter_amt` (started 2026-10-13 12:18; Control 30 : 36 : 36, A 16 : 40 : 40, and an exploratory 4 : 40 : 40). See Current status above. The headline metric is time to 90% of rise.
**Why:** finds the carryover that puts the peak at a convenient time at the lowest discard.
**Jars:** Control, A, B (add C in a later run if B peaks early).
**Output:** peak time for each ratio, per cycle.

### Run 2: Flour axis (best ratio from Run 1)
**Why:** flour changes speed, sourness, and how well the starter tolerates sitting past peak.
**Jars:** 100% whole wheat, 50/50 whole wheat/all-purpose, 100% all-purpose.
**Plan (set 2026-11-06; first set starts about 21:00 tonight, run name `run2_flour_axis`):**
- **Source starters (two Weck jars, fed on schedule so they can seed repeats; they are in camera view now and will be moved out of frame once the three experiment jars are set up):** whole wheat (King Arthur), fed about 09:00 on 11-06 (user's approximate time; the bread was made 09:00-09:30), weights not recorded, 100% hydration; and all-purpose (Gold Medal), fed 11:25 on 11-06 at 27 : 51 : 52, its third AP feed since the whole wheat carryover (earlier AP feeds 11-05 10:30 at 22 : 44 : 44 and 21:58 at 24 : 46 : 46). Both are clean single-flour starters (the AP jar's leftover whole wheat is under 1% after three AP feeds), so tonight's carryover does not contaminate any jar. The user judges their ripeness and handles them; they are in camera view for now.
- **Three experiment jars, in frame, left to right, fed within about 10 minutes of each other at about 21:00:** ratio A, 16 : 40 : 40 (96 g), 100% hydration, same jar type.

| Jar | Starter carryover | Flour | Water |
|---|---|---|---|
| Whole wheat | 16 g from the whole wheat jar | 40 g King Arthur whole wheat | 40 g |
| 50/50 | 8 g from the whole wheat jar + 8 g from the AP jar | 20 g whole wheat + 20 g Gold Medal AP | 40 g |
| All-purpose | 16 g from the AP jar | 40 g Gold Medal AP | 40 g |

  The 50/50 carryover is half of each so that it matches the flour mix; this was decided on 11-06 because the earlier notes did not specify it (confirmed by the user 2026-11-06).
- **Cycles:** cycle 1 is tonight's feed and shows each flour's immediate response. Cycle 2 is a second feed of the same three jars, same ratio and flour, with the same run name; it shows the adapted behavior (per the standard procedure). No new starter is needed for it.
- **Decision (user, 2026-11-11):** `run2_flour_axis_2` is the last flour-axis set (two cycles: 11-10 21:10-21:22 and 11-11 09:15-09:26); `run2b`/`run2c` are not planned. Next step is to home in on a flour mix, and the user will move to a single mother starter (the two-mother setup ends). Mix and design are not yet chosen.
- **Repeats (original plan, superseded by the decision above):** at least two independent sets on different nights (run names `run2b_flour_axis`, `run2c_flour_axis`), each seeded from freshly refreshed source jars, because two runs at a similar dilution have disagreed by over 1.5 h. The between-run spread is the main error.
- **Before starting:** set `input_text.starter_run` to `run2_flour_axis` (still `wheat_vs_AP_feed1` as of 11-06 midday); put a room thermometer in the pantry; check all three jars are in camera view; weigh each carryover by gross weight (Weck jar about 399 g).
- **Log for every jar:** gross weights, flour brand, position, time fed, time since each starter's last feed and its state, temperature, lids on or off.
- **Analysis:** `measure_heights.py` with jar columns taken from the first frame (the jar detector is unreliable on smeared glass, so check the QA sheet by eye); headline metric is time to 90% of the rise.
- **Temperature:** the Meater probe entities were already unavailable at 08:00 EST on 2026-11-05 (the start of the history window I queried, so the real onset is unknown) and stayed so through 11-06; nothing is logging jar temperature, so use a room thermometer.

#### wheat_vs_AP_feed1 observations (2026-11-05 10:30 to 2026-11-07 10:00, 95 frames, no gaps)
Two independent Weck-jar runs that happened to share the camera. Each jar's cycles are anchored to its own feed times in `data/feeds.csv`; the per-cycle numbers are in `results/wheat_vs_AP_feed1_cycles.csv`, and the per-frame wheat series is `wheat_vs_AP_feed1_height.csv`.
- **Method caveats:** the jars were handled and moved between frames (the right jar shifted about 90 px to the right around the 21:15 feed on 11-05; the pressure cooker behind them was removed on the morning of 11-07). The wheat series uses columns 2300-2470, which sit inside the jar before and after the move. The colour method is unreliable on the AP jar (smeared glass; it locks onto smear and reads the surface up to about 50 px too high), and the brightness method was erratic, so the AP cycles are read by eye from ruler crops, good to about +/- 10-15%. Frames at 09:30 and 10:00 on 11-07 are valid (the jars were not adjusted for feeding until between 10:00 and 10:30); the `*_height.csv` jar 1 column is therefore not trustworthy.
- **Wheat jar (right), per feed:** 10:30 on 11-05 (25 : 45 : 45): peak 19:30 (9 h), 1.46x, 90% at 8 h. 21:15 on 11-05 (35 : 83 : 84): peak about 08:00 (10.8 h), 1.61x, 90% at 8.2 h. About 09:00 on 11-06 (weights not recorded): flat until 14:00, 90% at 17:00 (8 h), 1.36x, plateau 18:00 to 04:00, then fell to about 81% of the peak by 10:00 on 11-07.
- **AP jar (left), per feed:** 10:30 on 11-05 (22 : 44 : 44, from the wheat starter): little rise before 15:00, peak about 19:00-21:00 (8.5-10.5 h), about 1.6x. 21:58 on 11-05 (24 : 46 : 46): slow start, peak about 07:00-09:00 (9-11 h), about 1.8x, down to about 80% by 11:00. 11:25 on 11-06 (27 : 51 : 52, about 21% carryover): peak about 18:00-22:00 (6.5-10.5 h), about 1.6x, sank to about 75% of the peak by 08:30 on 11-07 (22 h) without a collapse.
- **Pattern worth testing:** with similar carryover (about 17-21%), AP peaked later and more variably than wheat (9-11 h, with a long flat top) and sagged more slowly than wheat overnight; the wheat jar reached 90% of its rise within about 8 h each time. Two runs of the same feed differ by 1 h or more either way, so these are single observations.
- **Next feeds:** both jars were fed again for `wheat_vs_AP_feed2` at 10:13 (AP) and 10:19 (wheat) on 11-07, about 23 h and 25 h after their last feed.
- **Temperature:** none recorded (probe offline), so the pantry temperature is an unknown in all of these timings.

#### run2_flour_axis_2 observations (2026-11-10 21:10 to 2026-11-12 10:00, 74 frames at 30 min)
Second flour-axis set (wheat left, 50/50 middle, AP right; 16 : 40 : 40 each, plastic wrap on the tops). Readings are by eye from time-vs-row strips, +/-20 px, times +/-1 h; per-cycle numbers are in `data/cycles.csv`, key surface readings in `data/readings_by_eye.csv`.
- **Cycle 1 (fed 21:10-21:22):** refed at about 11.7 h while still rising (the 50/50 and AP steeply, at least 1.7x and 1.55x; wheat slowly, at least 1.5x), so ready and peak were not observed (lower bounds only). Set 1 peaked by about 10.5-11.2 h, so this was slower; no temperature recorded.
- **Cycle 2 (fed 09:15-09:26 on 11-11), per-frame read:** ready (90% of rise) 10 h 05 min (AP), 10 h 30 min (50/50), 12 h 45 min (wheat); peak about 12 h 10 min, 12 h 15 min and 15 h 05 min; rise 1.60x, 1.87x, 1.73x. So wheat was about 2-2.5 h slower than the other two to ripen, which is more than the +/-1 h reading error. At 24.6 h: wheat 0.87 of peak, 50/50 0.66, AP about 1.0 (flat top, no sag).
- **Hold order differs from set 1** (there wheat held best and AP sagged), so hold behavior is noisy. By-eye readings of every frame are in `docs/run2_flour_axis_2_by_eye.md`.
- **Design lesson:** a second feed at about 12 h cuts cycle 1 off before the peak when the starter is slower than expected; leave a cycle to run to its drop-off if the peak is the goal.
- **Decision:** this is the last flour-axis set (user, 2026-11-11); the next step is choosing a flour mix and moving to a single mother.

### Run 3: Sitting past peak
**Why:** checks whether a once-daily schedule is realistic, i.e. whether it collapses or recovers normally at the next feed.
**Jars:** 3 jars of the best ratio/flour combination, left the full 24 h between feeds.
**Check:** how far does it fall after peak, and does the next cycle rise normally?

### Run 4: Fridge and trip protocol
**Why:** to be sure the starter survives a long fridge stay and recovers.
**Feed before fridge** (per jar): about 5g starter + 30g flour + 25g water (a flour-heavy, slightly stiffer feed), 1 hour at room temp, then fridge.
**Jars:** one pulled after 7 days, one after 14 days.
**Recovery:** pull out, pour off any liquid, discard most of it, feed at room temperature. Log how many feedings until it peaks on its normal schedule again.

### Run 5: Real bake on the new routine
**Why:** a starter that behaves in a jar still has to make bread you like.
**Do:** build the levain at the scaled-up size from the best routine, bake the Perfect Loaf easy no-knead boule, compare to earlier loaves, and use the extra for crackers.

---

## Decision rules

Choose the routine where:

1. The peak lands inside AWAKE_WINDOW for the chosen FEED_TIME.
2. The carryover is as small as possible without being unreliable (jar-to-jar spread under about 1 h in Run 0 is the reference for what counts as reliable).
3. It still rises normally after sitting past peak (Run 3).
4. It survives the fridge trial (Run 4).
5. The bread is good (Run 5).

---

## Results log

| Run | Jar | Feed (g) | Flour | Feed time | Ready (90% of rise) | Peak time | Rise ratio | Hold time | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 0 repeat (pint) | 1 (left) | 30 : 35 : 35 | whole wheat (King Arthur) | 2026-10-12 21:50 | 8 h 35 min | 12 h 40 min | 1.26× | 4 h 00 min+ | pint-jar repeat; flat at the end of the photos; lag 2 h 55 min, half rise 5 h 45 min |
| 0 repeat (pint) | 2 (middle) | 30 : 36 : 38 | whole wheat (King Arthur) | 2026-10-12 21:50 | 8 h 50 min | 10 h 10 min | 1.35× | 1 h 30 min | pint-jar repeat; slightly wetter feed; half rise 6 h 25 min |
| 0 repeat (pint) | 3 (right) | 30 : 35 : 36 | whole wheat (King Arthur) | 2026-10-12 21:50 | 9 h 05 min | 11 h 40 min | 1.53× | 2 h 00 min | pint-jar repeat; highest rise, starting to fall at the end; half rise 6 h 00 min |
| 1 (starter amount) | 1 (left) | 30 : 36 : 36 | whole wheat (King Arthur) | 2026-10-13 12:18 | 9 h 00 min | 12 h 40 min | ~2.1x (method) | 4 h 00 min | brightness method; fell to ~1.9x by 25 h; half rise 6 h 30 min |
| 1 (starter amount) | 2 (middle) | 16 : 40 : 40 | whole wheat (King Arthur) | 2026-10-13 12:21 | 11 h 15 min | 19 h 40 min | 1.28x | 13 h 00 min+ | still flat at 25 h; half rise 7 h 10 min |
| 1 (starter amount) | 3 (right) | 4 : 40 : 40 | whole wheat (King Arthur) | 2026-10-13 12:26 | 15 h 55 min | 18 h 35 min | 1.31x | 7 h 30 min+ | 4 g carryover is unreliable (smear is a large part of the dose); half rise 10 h 25 min |
| Weck jar test | 1 | 77 : 102 : 102 | whole wheat (King Arthur) | 2026-10-07 21:50 | 6 h 55 min | 8 h 10 min | 1.54× | 3 h 00 min+ | first overnight test in a 280 g Weck jar; no collapse by the end of the photos |

Ready is the time to 90% of the total rise, interpolated from the smoothed series; it is far more repeatable than the peak time (jar-to-jar spread of about 15 min vs about 75 min in the pint run), so it is the number to schedule by. The three Bonne Maman jars of Run 0 (Oct 8-9) are left out of this log: the jars were uncovered and the scale was off (see `results/run0_bonne_maman_*` for the raw data).

\* rise under 10%: within measurement noise, peak and plateau times unreliable. Times are from the feed; "Feed (g)" is starter : flour : water; hold time is the plateau (within 2% of the peak).
