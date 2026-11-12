# run2_flour_axis_2: by-eye surface readings, every frame

Jars (data/feeds.csv): wheat (jar 3, left), 50/50 (jar 2, middle), AP (jar 1, right); 16 : 40 : 40 each (wheat 41 g water, cycle 2 wheat 17 g starter). Cycle 1 was fed 2026-11-10 21:10 (wheat), 21:16 (50/50) and 21:22 (AP); cycle 2 on 2026-11-11 at 09:26, 09:15 and 09:21. 74 frames from 2026-11-10 21:30 to 2026-11-12 10:00, one every 30 min, none missing. The machine-readable copy, with heights, is `results/run2_flour_axis_2_height.csv`; the dashboard charts come from it (`tools/summarize_run.py run2_flour_axis_2 --cycle K`).

## Method
- **Reading:** each jar's centre 60-80 px column was averaged per row and stacked in time order, so a jar's surface shows as a line across a strip. I read the surface row of every frame from 4x zoomed strips with a 10-row grid, as the top edge of the pale band of the dough surface.
- **Units:** rows of the full-resolution 3840 x 2160 frame; larger = lower in the frame. The dough bottom is taken as row 1890 (as in set 1), so dough height = 1890 - row.
- **Error:** about +/-10 px for sharp edges and +/-20 px where the edge is soft through glass haze (most of cycle 1, and the 50/50 and AP jars during their plateaus). That is about +/-0.1 to +/-0.2 in rise ratio; times are good to about +/-1 h.
- **One correction:** I first read the 50/50 jar as stepping down about 20 px between 04:30 and 05:00 on 11-12. A row brightness profile of those frames showed a real but smaller drop (about 13 px) and then a flat stretch, so the readings for 04:30 to 10:00 on 11-12 for that jar were revised to 1727, 1740, 1741, 1743, 1745, 1749, 1752, 1757, 1761, 1766, 1770, 1773. Nothing else was checked numerically.
- **Not measured:** the 09:30 frame on 11-11 is after all three refeeds, so it is the start of cycle 2 (the jars were handled, so the 09:30 reading is the least certain of that cycle). Temperature was not recorded.
- **Wrap and smear:** the jars were covered with plastic wrap and have starter smeared on the glass above the surface. The pale band includes some lit foam, so the "surface" is the top of that band, not a single sharp line.

## Results from these readings
Per-cycle numbers are in `data/cycles.csv`; cycle 1 is a lower bound because the refeed came before the 50/50 and AP peaks.

| Cycle 2 | Ready (90%) | Peak | Rise | Plateau | End vs peak |
|---|---|---|---|---|---|
| Wheat | 12 h 45 min | 15 h 05 min | 1.73x | 4 h 30 min | 0.87 |
| 50/50 | 10 h 30 min | 12 h 15 min | 1.87x | 1 h | 0.66 |
| AP | 10 h 05 min | 12 h 10 min | 1.60x | 13 h 30 min+ (flat to the end) | 1.00 |

## Surface row per frame
| Time | Cycle | Wheat (left) | 50/50 (middle) | AP (right) |
|---|---|---|---|---|
| 2026-11-10 21:30 | 1 | 1775 | 1778 | 1772 |
| 2026-11-10 22:00 | 1 | 1775 | 1778 | 1772 |
| 2026-11-10 22:30 | 1 | 1775 | 1778 | 1772 |
| 2026-11-10 23:00 | 1 | 1775 | 1778 | 1772 |
| 2026-11-10 23:30 | 1 | 1775 | 1778 | 1770 |
| 2026-11-11 00:00 | 1 | 1772 | 1777 | 1768 |
| 2026-11-11 00:30 | 1 | 1768 | 1775 | 1765 |
| 2026-11-11 01:00 | 1 | 1768 | 1773 | 1762 |
| 2026-11-11 01:30 | 1 | 1765 | 1771 | 1758 |
| 2026-11-11 02:00 | 1 | 1762 | 1768 | 1755 |
| 2026-11-11 02:30 | 1 | 1760 | 1763 | 1750 |
| 2026-11-11 03:00 | 1 | 1757 | 1757 | 1745 |
| 2026-11-11 03:30 | 1 | 1752 | 1752 | 1742 |
| 2026-11-11 04:00 | 1 | 1748 | 1745 | 1738 |
| 2026-11-11 04:30 | 1 | 1745 | 1740 | 1736 |
| 2026-11-11 05:00 | 1 | 1742 | 1733 | 1735 |
| 2026-11-11 05:30 | 1 | 1738 | 1727 | 1730 |
| 2026-11-11 06:00 | 1 | 1732 | 1722 | 1725 |
| 2026-11-11 06:30 | 1 | 1728 | 1718 | 1722 |
| 2026-11-11 07:00 | 1 | 1724 | 1713 | 1717 |
| 2026-11-11 07:30 | 1 | 1722 | 1710 | 1715 |
| 2026-11-11 08:00 | 1 | 1720 | 1707 | 1712 |
| 2026-11-11 08:30 | 1 | 1720 | 1700 | 1702 |
| 2026-11-11 09:00 | 1 | 1718 | 1695 | 1707 |
| 2026-11-11 09:30 | 2 | 1788 | 1795 | 1775 |
| 2026-11-11 10:00 | 2 | 1782 | 1795 | 1775 |
| 2026-11-11 10:30 | 2 | 1782 | 1795 | 1775 |
| 2026-11-11 11:00 | 2 | 1782 | 1795 | 1775 |
| 2026-11-11 11:30 | 2 | 1782 | 1795 | 1775 |
| 2026-11-11 12:00 | 2 | 1782 | 1793 | 1775 |
| 2026-11-11 12:30 | 2 | 1782 | 1793 | 1775 |
| 2026-11-11 13:00 | 2 | 1782 | 1792 | 1774 |
| 2026-11-11 13:30 | 2 | 1782 | 1790 | 1773 |
| 2026-11-11 14:00 | 2 | 1782 | 1788 | 1770 |
| 2026-11-11 14:30 | 2 | 1780 | 1783 | 1767 |
| 2026-11-11 15:00 | 2 | 1778 | 1778 | 1763 |
| 2026-11-11 15:30 | 2 | 1775 | 1773 | 1757 |
| 2026-11-11 16:00 | 2 | 1770 | 1768 | 1750 |
| 2026-11-11 16:30 | 2 | 1765 | 1760 | 1745 |
| 2026-11-11 17:00 | 2 | 1760 | 1752 | 1740 |
| 2026-11-11 17:30 | 2 | 1752 | 1745 | 1733 |
| 2026-11-11 18:00 | 2 | 1748 | 1735 | 1727 |
| 2026-11-11 18:30 | 2 | 1745 | 1730 | 1722 |
| 2026-11-11 19:00 | 2 | 1740 | 1727 | 1717 |
| 2026-11-11 19:30 | 2 | 1736 | 1722 | 1712 |
| 2026-11-11 20:00 | 2 | 1730 | 1718 | 1710 |
| 2026-11-11 20:30 | 2 | 1726 | 1716 | 1708 |
| 2026-11-11 21:00 | 2 | 1725 | 1713 | 1707 |
| 2026-11-11 21:30 | 2 | 1721 | 1712 | 1706 |
| 2026-11-11 22:00 | 2 | 1717 | 1712 | 1706 |
| 2026-11-11 22:30 | 2 | 1713 | 1718 | 1708 |
| 2026-11-11 23:00 | 2 | 1710 | 1717 | 1712 |
| 2026-11-11 23:30 | 2 | 1712 | 1717 | 1712 |
| 2026-11-12 00:00 | 2 | 1709 | 1717 | 1712 |
| 2026-11-12 00:30 | 2 | 1708 | 1717 | 1712 |
| 2026-11-12 01:00 | 2 | 1706 | 1717 | 1712 |
| 2026-11-12 01:30 | 2 | 1710 | 1718 | 1713 |
| 2026-11-12 02:00 | 2 | 1709 | 1720 | 1713 |
| 2026-11-12 02:30 | 2 | 1710 | 1721 | 1713 |
| 2026-11-12 03:00 | 2 | 1710 | 1722 | 1715 |
| 2026-11-12 03:30 | 2 | 1711 | 1724 | 1717 |
| 2026-11-12 04:00 | 2 | 1710 | 1726 | 1717 |
| 2026-11-12 04:30 | 2 | 1713 | 1727 | 1720 |
| 2026-11-12 05:00 | 2 | 1714 | 1740 | 1717 |
| 2026-11-12 05:30 | 2 | 1717 | 1741 | 1717 |
| 2026-11-12 06:00 | 2 | 1718 | 1743 | 1715 |
| 2026-11-12 06:30 | 2 | 1721 | 1745 | 1710 |
| 2026-11-12 07:00 | 2 | 1722 | 1749 | 1708 |
| 2026-11-12 07:30 | 2 | 1723 | 1752 | 1710 |
| 2026-11-12 08:00 | 2 | 1725 | 1757 | 1708 |
| 2026-11-12 08:30 | 2 | 1726 | 1761 | 1706 |
| 2026-11-12 09:00 | 2 | 1728 | 1766 | 1706 |
| 2026-11-12 09:30 | 2 | 1731 | 1770 | 1706 |
| 2026-11-12 10:00 | 2 | 1732 | 1773 | 1706 |
