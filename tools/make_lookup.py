#!/usr/bin/env python3
"""Derive data/lookup_ready_times.csv from data/cycles.csv and data/feeds.csv (a derived file: do not edit).

Cycles with include_in_lookup=1 and a 90% time are grouped by flour class and carryover bucket
(starter / total). Time-like values (ready, peak, plateau) and the rise ratio are averaged with the
geometric mean, because fermentation time scales multiplicatively (a few hours slower is about the same
proportional effect at any dilution) and the spread is skewed; the arithmetic mean of 8 h and 16 h is 12 h,
the geometric mean 11.3 h. `ready_gsd` is the geometric standard deviation, a factor: about 68% of cycles fall
within ready_gmean_h / gsd to ready_gmean_h * gsd (blank when n < 2). Temperature is averaged arithmetically.
"""
import csv, math
from pathlib import Path
D = Path(__file__).resolve().parent.parent / 'data'
B = [(0, .10, '<10%'), (.10, .15, '10-15%'), (.15, .20, '15-20%'), (.20, .25, '20-25%'), (.25, 1.01, '25%+')]


def gmean(v):
    return math.exp(sum(map(math.log, v)) / len(v))


def gsd(v):
    if len(v) < 2:
        return ''
    m = sum(map(math.log, v)) / len(v)
    return round(math.exp(math.sqrt(sum((math.log(x) - m) ** 2 for x in v) / (len(v) - 1))), 2)


feeds = {r['feed_id']: r for r in csv.DictReader(open(D / 'feeds.csv'))}
g = {}
for c in csv.DictReader(open(D / 'cycles.csv')):
    f = feeds[c['feed_id']]
    if c['include_in_lookup'] != '1' or c['ready_90_h'] == '' or f['carryover_frac'] == '':
        continue
    frac = float(f['carryover_frac'])
    lab = next(l for lo, hi, l in B if lo <= frac < hi)
    g.setdefault((f['flour_class'], lab), []).append(c)
order = {l: i for i, (_, _, l) in enumerate(B)}


def col(rs, k):
    return [float(r[k]) for r in rs if r[k] != '']


rows = []
for (fl, lab), rs in sorted(g.items(), key=lambda kv: (kv[0][0], order[kv[0][1]])):
    rd, pk = col(rs, 'ready_90_h'), col(rs, 'peak_h')
    pl = [float(r['plateau_h']) for r in rs if r['plateau_h'] != '' and r['plateau_open'] == '0']
    rr, tp = col(rs, 'rise_ratio'), col(rs, 'temp_f_mean')
    rows.append(dict(flour_class=fl, carryover_bucket=lab, n=len(rs),
                     ready_gmean_h=round(gmean(rd), 1), ready_gsd=gsd(rd),
                     peak_gmean_h=round(gmean(pk), 1) if pk else '',
                     plateau_gmean_h_closed=round(gmean(pl), 1) if pl else '',
                     n_plateau_open=sum(1 for r in rs if r['plateau_open'] == '1'),
                     rise_ratio_gmean=round(gmean(rr), 2) if rr else '',
                     temp_f_mean=round(sum(tp) / len(tp), 1) if tp else '',
                     runs=';'.join(sorted({r['run_id'] for r in rs}))))
with open(D / 'lookup_ready_times.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r['flour_class'], r['carryover_bucket'], 'n', r['n'], 'ready', r['ready_gmean_h'], 'gsd', r['ready_gsd'], 'peak', r['peak_gmean_h'])
