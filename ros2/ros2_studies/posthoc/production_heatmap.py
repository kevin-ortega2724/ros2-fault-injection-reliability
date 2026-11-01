"""Mapa de calor del tiempo detenido por minuto en cada réplica de E1b, a partir de los registros congelados; no añade datos."""
import csv
import glob
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ORDER, RESULTS  # noqa: E402

FIG = HERE / 'results'
INK, MUTED = '#0b0b0b', '#52514e'
RAMP = LinearSegmentedColormap.from_list('stop', ['#f6f5f1', '#f4b48e', '#eb6834', '#8f3210', '#3a1405'])
MINUTES, HOLD = 48, 60.0
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': MUTED, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED})


def events(path):
    """Cambios de estado y último evento; un incidente deja la celda detenida hasta declararse (al menos HOLD s)."""
    up, last, incident = [], 0.0, False
    for line in Path(path).read_text().splitlines():
        if line.startswith('INCIDENTE'):
            incident = True
        m = re.match(r'(\d+\.\d+) (.*)', line)
        if m:
            last = float(m.group(1))
            if m.group(2) in ('MARCHA', 'PARO'):
                up.append((last, m.group(2) == 'MARCHA'))
    return up, last, incident


def stopped_per_minute(config, replica):
    """Concatena los intentos de una réplica; devuelve fracción detenida por minuto y minutos con incidente."""
    seg, marks, offset = [], [], 0.0
    for path in sorted(glob.glob(str(RESULTS / f'cell_{replica}_{config}_a*.log'))):
        up, last, incident = events(path)
        marchas = [t for t, s in up if s]
        if not marchas:
            continue
        start, end = marchas[0], last + (HOLD if incident else 0.0)
        state, cursor = True, start
        for t, s in [(t, s) for t, s in up if t > start] + [(end, None)]:
            seg.append((offset + cursor - start, offset + t - start, state))
            cursor, state = t, s
        offset += end - start
        if incident:
            marks.append(offset / 60)
    grid = np.full(MINUTES, np.nan)
    for m in range(MINUTES):
        a, b = m * 60.0, (m + 1) * 60.0
        if offset >= b:
            grid[m] = sum(max(0.0, min(e, b) - max(s, a)) for s, e, on in seg if not on) / 60
    return grid, marks


rows, labels, marks = [], [], []
for c in ORDER:
    for r in (1, 2, 3):
        g, m = stopped_per_minute(c, r)
        rows.append(g)
        labels.append((c, r))
        marks.append(m)
grid = np.array(rows)
with open(HERE / 'results' / 'E1b_stopped_per_minute.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['config', 'replica', *range(MINUTES)])
    for (c, r), g in zip(labels, grid):
        w.writerow([c, r, *[f'{v:.4f}' if np.isfinite(v) else '' for v in g]])
    for (c, r), m in zip(labels, marks):
        print(c, r, 'detenido', round(float(np.nanmean(grid[labels.index((c, r))])), 3), 'min completos', int(np.isfinite(grid[labels.index((c, r))]).sum()), 'incidentes', np.round(m, 1))

fig, ax = plt.subplots(figsize=(6.3, 3.6))
cmap = RAMP.copy()
cmap.set_bad('#ffffff')
im = ax.imshow(100 * grid, aspect='auto', cmap=cmap, vmin=0, vmax=100, interpolation='nearest', extent=(0, MINUTES, len(rows), 0))
for i, m in enumerate(marks):
    for x in m:
        ax.plot([x], [i + .5], marker='v', ms=4.5, color='white', mec=INK, mew=.8, clip_on=False, zorder=5)
for k in range(1, len(ORDER)):
    ax.axhline(3 * k, color='white', lw=2.5)
ax.set_yticks([3 * k + 1.5 for k in range(len(ORDER))], ORDER, family='monospace')
ax.set_xlabel('Time since the cell first ran (min)')
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.plot([], [], marker='v', ms=4.5, ls='', color='white', mec=INK, mew=.8, label='Incident (domain restarted)')
ax.legend(frameon=False, loc='lower center', bbox_to_anchor=(.5, 1.0), labelcolor=MUTED)
cb = fig.colorbar(im, ax=ax, pad=.02, fraction=.03)
cb.set_label('Cell stopped (% of the minute)')
cb.outline.set_visible(False)
fig.tight_layout()
fig.savefig(FIG / 'stopped_heatmap.pdf')
