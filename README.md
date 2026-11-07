# Sourdough

Starter experiments: how feed ratio and flour change the time to ripe. The end goal is a lookup (flour mix, starter / flour / water grams) -> time to 90% of the rise ("ready") and, if possible, how long it stays on the plateau.

Home Assistant runs the camera and notifications and lives in `~/GIT/ha-repo`; this repo holds the data and analysis.

## Data (`data/`, plain CSV, edited directly)

| Table | One row per | What it holds |
|---|---|---|
| `runs.csv` | run | kind, jar type, dates |
| `feeds.csv` | feed of one jar | the inputs (below) |
| `cycles.csv` | measured rise after a feed | the outcomes (below); keyed to `feeds.csv` by `feed_id` |
| `frames.csv` | photo of one jar | measured dough height; `quality` = ok or unreliable |
| `readings_by_eye.csv` | hand reading | for jars the detector cannot measure (smeared glass) |
| `annotations.csv` | event or caveat | handling, unrecorded feeds, outages |
| `lookup_ready_times.csv` | flour x carryover bucket | derived by `tools/make_lookup.py`; do not edit |

**`feeds.csv` (inputs):** `starter_g`, `starter_source` (which jar the carryover came from) and `starter_ww_frac` (share of the starter's flour that is whole wheat; 1.0 for whole wheat starters, estimated for the AP jar that began as wheat), `flour_name` (brand and kind as logged), `flour_class` (`whole_wheat`, `ap` or `mixed`), `flour_ww_g` and `flour_ap_g` (grams of each, so 50/50 jars fit), `flour_g` (total), `water_g` (`water_g_raw` keeps a logged range), then derived `total_g`, `carryover_frac`, `hydration` and `whole_wheat_frac`. `complete` is 0 when weights are missing.

**`cycles.csv` (outcomes):** hours from the feed to `lag_h`, `half_rise_h`, `ready_90_h` (90% of the rise, the headline number), `peak_h` with `peak_h_min` / `peak_h_max` (the peak is approximate and often a range), `plateau_h` (`plateau_open` = 1 means it was still going when the data ended), `rise_ratio`, `end_over_peak`. Temperature: `temp_f_mean` (mean pantry temperature over the cycle) and `temp_source` (probe, thermostat proxy, thermometer, or blank). `include_in_lookup` and `exclude_reason` are editable.

Conventions: local time, grams, hours from the feed. `carryover_frac` = starter / (starter + flour + water). `hydration` = (water + starter/2) / (flour + starter/2). Approximate values are fine; say so in `notes`. Missing is blank, never guessed.

## Lookup

`tools/make_lookup.py` averages `ready_90_h` and the other time-like values with the **geometric mean** and reports `ready_gsd`, a multiplicative spread factor (1.25 means about a quarter above or below), on the working assumption that temperature and starter vigor change times by a factor. It is a modelling choice; at today's spread it differs from the arithmetic mean by about 0.1 h. To be revisited when there is enough data to fit. Temperature is averaged normally. No min/max.

```
tools/make_lookup.py
```

## Caveats worth knowing

- No jar temperature exists for any cycle yet (the Meater probe was offline from 2026-11-05); `temp_f_mean` is blank.
- Jars get moved between frames; check jar x-positions before trusting heights. The AP jar of `wheat_vs_AP_feed1` is read by eye.
- Run-to-run spread is large: the same 17% carryover took 11.3 h (pint jar, Oct) and 8.2 h (Weck jar, Nov), so a lookup cell is a range, not a point.
