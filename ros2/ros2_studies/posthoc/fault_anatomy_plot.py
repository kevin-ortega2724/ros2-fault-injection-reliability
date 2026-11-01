"""Figura y tiempos de fault_anatomy.py. Se muestra la primera inyección con el brazo en movimiento en cada arquitectura."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / 'results'
FIG = HERE / 'results'
INK, MUTED, GRID, COL_A, COL_B = '#0b0b0b', '#52514e', '#e4e3df', '#2a78d6', '#eb6834'
MOVING, STILL, BEFORE, AFTER = 0.05, 0.02, 3.0, 12.0
CASES = {'d_series': 'l12', 'd_parallel': 'la'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': MUTED, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})


def load(config):
    beats, qt, q, up = [], [], [], []
    for line in (RES / f'anatomy_{config}.ctrl.log').read_text().splitlines():
        p = line.split()
        if len(p) < 2:
            continue
        if p[1] == 'beat':
            beats.append(float(p[0]))
        elif p[1] == 'q':
            qt.append(float(p[0]))
            q.append([float(v) for v in p[2:]])
        elif p[1] == 'ev' and p[2] in ('MARCHA', 'PARO'):
            up.append((float(p[0]), p[2] == 'MARCHA'))
    kills, spawns = [], []
    for line in (RES / f'anatomy_{config}.faults.log').read_text().splitlines():
        t, what, _ = line.split()
        (kills if what == 'kill' else spawns).append(float(t))
    qt, q = np.array(qt), np.array(q)
    # velocidad articular máxima, con diferencias sobre 0.1 s para quitar el ruido de muestreo
    step = max(1, int(round(0.1 / np.median(np.diff(qt)))))
    speed = np.abs(q[step:] - q[:-step]).max(axis=1) / (qt[step:] - qt[:-step])
    return np.array(beats), qt[step:], speed, up, np.array(kills), np.array(spawns)


def per_injection(config):
    beats, qt, speed, up, kills, spawns = load(config)
    rows = []
    for i, (k, s) in enumerate(zip(kills, spawns)):
        end = kills[i + 1] if i + 1 < len(kills) else k + 25
        paro = [t for t, on in up if not on and k <= t < end]
        marcha = [t for t, on in up if on and paro and paro[0] < t < end]
        moving = bool((speed[(qt > k - .2) & (qt <= k)] > MOVING).any())
        gaps = np.diff(beats[(beats > k - 1) & (beats < end)])
        row = {'config': config, 'injection': i, 'kill': k, 'arm_moving': moving, 'stops': len(paro), 'max_beat_gap': gaps.max() if len(gaps) else np.nan,
               'last_beat': np.nan, 'to_stop': np.nan, 'to_still': np.nan, 'to_beat': np.nan, 'to_run': np.nan}
        if paro:
            last = beats[beats < paro[0]].max()
            first = beats[beats > s].min()
            row.update(last_beat=last - k, to_stop=paro[0] - k, to_beat=first - s, to_run=marcha[0] - k if marcha else np.nan)
            if moving:
                after = qt[(qt > paro[0]) & (speed < STILL)]
                row['to_still'] = after.min() - k if len(after) else np.nan
        rows.append(row)
    return rows


all_rows = [r for c in CASES for r in per_injection(c)]
with open(RES / 'anatomy_injections.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=all_rows[0].keys())
    w.writeheader()
    w.writerows(all_rows)
for c in CASES:
    rows = [r for r in all_rows if r['config'] == c]
    print(c, 'inyecciones', len(rows), 'con paro', sum(r['stops'] > 0 for r in rows), 'paros', sum(r['stops'] for r in rows), 'brazo en movimiento', sum(r['arm_moving'] for r in rows),
          'hueco máximo', round(max(r['max_beat_gap'] for r in rows), 3), 'mediana hueco', round(float(np.median([r['max_beat_gap'] for r in rows])), 3))
    for key in ('last_beat', 'to_stop', 'to_still', 'to_beat', 'to_run'):
        v = np.array([r[key] for r in rows], float)
        v = v[np.isfinite(v)]
        if len(v):
            print(' ', key, 'n', len(v), 'mediana', round(float(np.median(v)), 3), 'min', round(float(v.min()), 3), 'max', round(float(v.max()), 3))

fig, axes = plt.subplots(3, 2, figsize=(6.3, 3.5), sharex=True, sharey='row', gridspec_kw={'height_ratios': (.55, 1.5, .4), 'hspace': .16, 'wspace': .06})
for col, (config, victim) in enumerate(CASES.items()):
    beats, qt, speed, up, kills, spawns = load(config)
    i = next(j for j, r in enumerate(r for r in all_rows if r['config'] == config) if r['arm_moving'])
    k, s = kills[i], spawns[i]
    print(config, 'mostrada', i)
    ax_b, ax_v, ax_s = axes[:, col]
    win = (beats >= k - BEFORE) & (beats <= k + AFTER)
    ax_b.vlines(beats[win] - k, 0, 1, color=MUTED, lw=.3)
    mask = (qt >= k - BEFORE) & (qt <= k + AFTER)
    ax_v.plot(qt[mask] - k, speed[mask], color=COL_A, lw=1.3)
    ax_s.set_xlim(-BEFORE, AFTER)
    state = [on for t, on in up if t <= k - BEFORE][-1]
    edges = [-BEFORE] + [t - k for t, _ in up if k - BEFORE < t < k + AFTER] + [AFTER]
    for a, b in zip(edges, edges[1:]):
        ax_s.barh(0, b - a, left=a, height=1, color=GRID if state else COL_B, edgecolor='white', lw=.6)
        ax_s.text((a + b) / 2 if b - a < AFTER else 8.0, 0, 'RUN' if state else 'STOP', ha='center', va='center', fontsize=7, color=INK)
        state = not state
    for ax in (ax_b, ax_v, ax_s):
        ax.axvline(0, color=INK, lw=.9)
        ax.axvline(s - k, color=MUTED, lw=.9, ls=':')
    ax_b.set_title(f'{config}: SIGKILL to {victim}', fontsize=8, color=INK, family='monospace', loc='left', pad=11)
    ax_b.text(0, 1.04, 'kill', transform=ax_b.get_xaxis_transform(), ha='center', va='bottom', fontsize=7, color=INK)
    ax_b.text(s - k, 1.04, 'restart', transform=ax_b.get_xaxis_transform(), ha='center', va='bottom', fontsize=7, color=MUTED)
    ax_b.set_ylim(0, 1)
    ax_s.set_ylim(-.5, .5)
    ax_v.grid(axis='y', color=GRID, lw=.5)
    ax_v.set_axisbelow(True)
    ax_s.set_xlabel('Time from fault injection (s)')
    for ax in (ax_b, ax_s):
        ax.set_yticks([])
        ax.spines['left'].set_visible(False)
    ax_b.spines['bottom'].set_visible(False)
    ax_b.tick_params(length=0)
axes[0, 0].set_ylabel('Signal', rotation=0, ha='right', va='center')
axes[1, 0].set_ylabel('Arm joint speed\n(rad/s)')
axes[2, 0].set_ylabel('Cell', rotation=0, ha='right', va='center')
fig.subplots_adjust(left=.13, right=.99, top=.9, bottom=.13)
fig.savefig(FIG / 'fault_anatomy.pdf')

# fotogramas de fault_frames.py, con la baliza ampliada
fig, axes = plt.subplots(2, 2, figsize=(6.3, 3.75), gridspec_kw={'wspace': .03, 'hspace': .1})
TIMES = {'d_series': ('−0.09 s', '+2.54 s: stopped'), 'd_parallel': ('−0.11 s', '+2.52 s: running')}
for row, config in enumerate(CASES):
    for col, label in enumerate(('before', 'after')):
        ax = axes[row, col]
        im = plt.imread(RES / f'frame_{config}_{label}.jpg')
        ax.imshow(im[230:930, 130:1400], interpolation='lanczos')
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.text(.01, .98, f'{config}, t = {TIMES[config][col]}', transform=ax.transAxes, va='top', fontsize=7, color=INK, family='monospace',
                bbox={'fc': 'white', 'ec': 'none', 'alpha': .85, 'pad': 1.5})
        inset = ax.inset_axes((.91, .62, .08, .36))
        inset.imshow(im[300:385, 266:296], interpolation='lanczos')
        inset.set_xticks([])
        inset.set_yticks([])
fig.subplots_adjust(left=.005, right=.995, top=.995, bottom=.005)
fig.savefig(FIG / 'fault_frames.png', dpi=260)
