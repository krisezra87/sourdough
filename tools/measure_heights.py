#!/usr/bin/env python3
"""Measure dough height in each jar of each frame of a run.

Usage:
  tools/measure_heights.py <run> --jar 1:1820-1990 --jar 2:2250-2420 --jar 3:2680-2850
                             [--rows 1550-1950] [--qa] [--skip YYYYMMDD_HHMM ...]

  --jar N:x0-x1   pixel columns (full-resolution frame) inside jar N's glass;
                  N:x0-x1:y0-y1 also gives that jar its own rows, for a jar whose
                  smears sit above the dough and fool the detector
  --rows y0-y1    pixel rows to look at (default 1550-1950)
  --skip STEM     leave out a frame (name without .jpg), e.g. one shot before the
                  camera was bumped back into place; repeatable
  --lum N         measure jar N by brightness instead of colour: the dough is darker
                  than the glass above it, so the surface is where the row-mean
                  brightness first falls to halfway between the glass above and the
                  dough below. Use for a jar whose glass is smeared with dough-
                  coloured residue (needs N:x0-x1:y0-y1 rows; the bottom is taken
                  as 40 rows above the end of the band)
  --qa            also write a contact sheet with the detected surface drawn on
                  (results/<run>_qa.jpg) so a person can check by eye

Reads   photos/<run>/2*.jpg   (frames named YYYYMMDD_HHMM.jpg)
Writes  results/<run>_height.csv  with columns
        time_local, jar, surface_row_px, bottom_row_px, dough_height_px, height_vs_start

Method: dough is warm-coloured (red minus blue is high) against clear glass and a
dark counter. Per jar and frame, the mean red-minus-blue per pixel row is
smoothed; the bright pale top layer of the dough is its peak, and the surface is
where that signal first falls to half its peak going up. The bottom is the median
over all frames of the last warm row. height_vs_start is relative to the mean of
that jar's first two frames. Frames that are not colour (infrared) are skipped.
"""
import csv, statistics, sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent  # repo root; photos/ and results/ live there


def parse_range(s):
    a, b = s.split("-")
    return int(a), int(b)


def colourfulness(a):
    return float(np.abs(a[:, :, 0] - a[:, :, 2]).mean())


def measure_jar_lum(a, x0, x1, y0, y1):
    seg = a[y0:y1, x0:x1]
    lum = (0.299 * seg[:, :, 0] + 0.587 * seg[:, :, 1] + 0.114 * seg[:, :, 2]).mean(axis=1)
    p = np.convolve(lum, np.ones(9) / 9, mode="same")
    n = len(p)
    glass, dough = p[10:50].mean(), p[n - 100:n - 50].mean()
    thr = (glass + dough) / 2
    for i in range(10, n - 25):
        if p[i] < thr and p[i:i + 15].mean() < thr:
            return i + y0, y1 - 40
    return y0, y1 - 40


def measure_jar(a, x0, x1, y0, y1, margin=60):
    seg = a[y0:y1, x0:x1]
    rb = np.convolve((seg[:, :, 0] - seg[:, :, 2]).mean(axis=1), np.ones(9) / 9, mode="same")
    lo, hi = margin, len(rb) - 90                   # keep away from the frame edges of the band
    p = lo + int(np.argmax(rb[lo:hi]))
    i = p
    while i > 0 and rb[i] > 0.5 * rb[p]:
        i -= 1
    bot = max(k for k in range(len(rb)) if rb[k] > 8)
    return i + y0, bot + y0


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    run = argv[0]
    jars, rows_rng, qa, skip, jar_rows, lum = {}, (1550, 1950), False, set(), {}, set()
    k = 1
    while k < len(argv):
        if argv[k] == "--jar":
            n, rng, *rows = argv[k + 1].split(":")
            jars[int(n)] = parse_range(rng)
            if rows:
                jar_rows[int(n)] = parse_range(rows[0])
            k += 2
        elif argv[k] == "--rows":
            rows_rng = parse_range(argv[k + 1]); k += 2
        elif argv[k] == "--lum":
            lum.add(int(argv[k + 1])); k += 2
        elif argv[k] == "--skip":
            skip.add(argv[k + 1]); k += 2
        elif argv[k] == "--qa":
            qa = True; k += 1
        else:
            sys.exit(f"unknown argument {argv[k]}")
    if not jars:
        sys.exit("give at least one --jar N:x0-x1")

    files = sorted((ROOT / "photos" / run).glob("2*.jpg"))
    y0, y1 = rows_rng
    per = {j: [] for j in jars}        # j -> [(time, surface, bottom)]
    frames = []
    for f in files:
        if f.stem in skip:
            continue
        img = Image.open(f).convert("RGB")
        a = np.asarray(img, dtype=float)
        if colourfulness(a) < 3:
            print(f"skipping non-colour frame {f.name}", file=sys.stderr)
            continue
        t = datetime.strptime(f.name[:13], "%Y%m%d_%H%M")
        frames.append((t, f))
        for j, (x0, x1) in jars.items():
            if j in lum:
                s, b = measure_jar_lum(a, x0, x1, *jar_rows[j])
            elif j in jar_rows:     # rows chosen by hand: trust them right up to their top edge
                s, b = measure_jar(a, x0, x1, *jar_rows[j], margin=15)
            else:
                s, b = measure_jar(a, x0, x1, y0, y1)
            per[j].append((t, s, b))

    out = ROOT / "results" / f"{run}_height.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time_local", "jar", "surface_row_px", "bottom_row_px", "dough_height_px", "height_vs_start"])
        for j in sorted(per):
            bot = statistics.median(b for _, _, b in per[j])
            hs = [bot - s for _, s, _ in per[j]]
            base = statistics.mean(hs[:2])
            for (t, s, _), h in zip(per[j], hs):
                w.writerow([t.strftime("%Y-%m-%d %H:%M"), j, s, int(bot), int(h), round(h / base, 3)])
    print(f"wrote {out} ({len(frames)} frames, {len(jars)} jars)")

    if qa:
        step = max(1, len(frames) // 12)
        pick = list(range(0, len(frames), step))
        x_lo = min(x0 for x0, _ in jars.values()) - 40
        x_hi = max(x1 for _, x1 in jars.values()) + 40
        tiles = []
        for idx in pick:
            t, f = frames[idx]
            im = Image.open(f).convert("RGB").crop((x_lo, y0, x_hi, y1))
            d = ImageDraw.Draw(im)
            for j, (x0, x1) in jars.items():
                s = per[j][idx][1]
                d.line((x0 - x_lo, s - y0, x1 - x_lo, s - y0), fill=(255, 0, 0), width=3)
            d.rectangle((0, 0, 190, 30), fill="black")
            d.text((8, 8), t.strftime("%m-%d %H:%M"), fill="white")
            tiles.append(im.resize((im.width // 3, im.height // 3)))
        cols = 3
        rows = (len(tiles) + cols - 1) // cols
        tw, th = tiles[0].size
        sheet = Image.new("RGB", (cols * tw, rows * th))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
        qa_path = ROOT / "results" / f"{run}_qa.jpg"
        sheet.save(qa_path, quality=85)
        print(f"wrote {qa_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
