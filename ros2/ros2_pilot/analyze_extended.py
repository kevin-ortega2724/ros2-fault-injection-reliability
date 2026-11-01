"""Análisis exploratorio, no prerregistrado: distribuciones, sensibilidad a L y figuras."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kstest

from configs import CONFIGS, SINK, SOURCE
from predict import first_passage_cdf, mfpt

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
FIG = HERE / 'results' / 'figures'
FIG.mkdir(exist_ok=True)
LAM, MTTR = 1 / 60, 4.0
ORDER = ['d_series', 'd_parallel', 'd_triangle', 'd_units', 'r2oo3', 'cen']
INK, MUTED, GRID, COL_A, COL_B = '#0b0b0b', '#52514e', '#e4e3df', '#2a78d6', '#eb6834'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': MUTED, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
lat = np.array(json.loads((OUT / 'latency.json').read_text()))
L = lat.mean()
mu = 1 / (MTTR + L)
data = {c: pd.read_csv(OUT / f'trials_{c}.csv') for c in ORDER}
summary = pd.read_csv(OUT / 'summary.csv').set_index('config')


def holm(p):
    p = np.asarray(p)
    adj, peak = np.empty(len(p)), 0.0
    for rank, i in enumerate(np.argsort(p)):
        peak = max(peak, min(1.0, (len(p) - rank) * p[i]))
        adj[i] = peak
    return adj


rows = []
for c in ORDER:
    x = data[c].t_obs.to_numpy()
    for rule, series in (('A', False), ('B', True)):
        r = kstest(x, lambda t, s=series, cfg=CONFIGS[c]: first_passage_cdf(cfg, LAM, mu, np.atleast_1d(t), s))
        rows.append({'config': c, 'rule': rule, 'ks_D': r.statistic, 'p': r.pvalue})
ks = pd.DataFrame(rows)
ks['p_holm'] = holm(ks.p)
ks.to_csv(OUT / 'ks_tests.csv', index=False)
print(ks.round(4).to_string(index=False))

sens = []
for c in ORDER:
    row = {'config': c}
    for name, v in (('p05', np.percentile(lat, 5)), ('mean', L), ('p95', np.percentile(lat, 95))):
        row[f'A_{name}'] = mfpt(CONFIGS[c], LAM, 1 / (MTTR + v))
    sens.append(row)
sens = pd.DataFrame(sens)
sens.to_csv(OUT / 'sensitivity_latency.csv', index=False)
print(sens.round(2).to_string(index=False), '\nL p05/p95', np.percentile(lat, [5, 95]).round(3))

# observado frente a predicciones
fig, ax = plt.subplots(figsize=(6.3, 2.7))
for i, c in enumerate(ORDER[::-1]):
    s = summary.loc[c]
    ax.plot([s.ci_lo, s.ci_hi], [i, i], color=MUTED, lw=2, solid_capstyle='round', zorder=1)
    ax.scatter(s.obs_mean, i, s=36, color=INK, zorder=3, label='Observed mean, 95% CI' if i == 0 else None)
    ax.scatter(s.pred_B, i, s=46, marker='s', color=COL_B, edgecolor='#fcfcfb', lw=.8, zorder=4, label='B: links in series' if i == 0 else None)
    ax.scatter(s.pred_A, i, s=46, marker='D', color=COL_A, edgecolor='#fcfcfb', lw=.8, zorder=5, label='A: graph logic' if i == 0 else None)
ax.set_yticks(range(6), ORDER[::-1], family='monospace')
ax.set_xlabel('Mean time to loss of function (s)')
ax.set_xlim(0, 72)
ax.grid(axis='x', color=GRID, lw=.6)
ax.set_axisbelow(True)
ax.tick_params(length=0)
h, l = ax.get_legend_handles_labels()
fig.legend(h, l, frameon=False, ncol=3, loc='upper center', labelcolor=MUTED)
fig.tight_layout(rect=(0, 0, 1, .92))
fig.savefig(FIG / 'obs_vs_pred.pdf')

# curvas de primer paso
fig, axes = plt.subplots(2, 3, figsize=(6.3, 3.6), sharey=True)
for ax, c in zip(axes.flat, ORDER):
    x = np.sort(data[c].t_obs.to_numpy())
    grid = np.linspace(0, x.max(), 90)
    ax.plot(grid, first_passage_cdf(CONFIGS[c], LAM, mu, grid, True), color=COL_B, lw=2, ls=(0, (4, 2)), label='B: links in series')
    ax.plot(grid, first_passage_cdf(CONFIGS[c], LAM, mu, grid), color=COL_A, lw=2, label='A: graph logic')
    ax.step(np.r_[0, x], np.arange(len(x) + 1) / len(x), where='post', color=INK, lw=1, label='Observed')
    ax.set_title(c, family='monospace', fontsize=8, color=INK, loc='left')
    ax.grid(color=GRID, lw=.5)
    ax.set_axisbelow(True)
    ax.set_ylim(0, 1)
for ax in axes[1]:
    ax.set_xlabel('Time (s)')
for ax in axes[:, 0]:
    ax.set_ylabel('P(function lost)')
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h[::-1], l[::-1], frameon=False, ncol=3, loc='upper center', labelcolor=MUTED)
fig.tight_layout(rect=(0, 0, 1, .94))
fig.savefig(FIG / 'first_passage.pdf')

# diagramas generados desde configs.py
fig, axes = plt.subplots(2, 3, figsize=(6.3, 3.0))
for ax, c in zip(axes.flat, ORDER):
    cfg = CONFIGS[c]
    depth = {SOURCE: 0}
    for _ in cfg:
        for n, comp in cfg.items():
            depth[n] = 1 + max(depth.get(i, 0) for i in comp.inputs)
    cols = {}
    for n, d in depth.items():
        cols.setdefault(d, []).append(n)
    pos = {n: (d, (len(ns) - 1) / 2 - k) for d, ns in cols.items() for k, n in enumerate(ns)}
    for n, comp in cfg.items():
        for i in comp.inputs:
            ax.annotate('', pos[n], pos[i], arrowprops=dict(arrowstyle='-|>', color=MUTED, lw=.7, shrinkA=8, shrinkB=8))
    for n, (x, y) in pos.items():
        link = n in cfg and cfg[n].is_link
        fixed = n in (SOURCE, SINK)
        ax.text(x, y, f'{n}\n{cfg[n].k}/{len(cfg[n].inputs)}' if n in cfg and cfg[n].k > 1 else n, ha='center', va='center',
                fontsize=6, color=INK, bbox=dict(boxstyle='round,pad=.3', fc='#f0efec' if fixed else '#cde2fb' if not link else '#fbdccf',
                                                 ec=MUTED, lw=.5, ls='--' if link else '-'))
    ax.set_title(c, family='monospace', fontsize=8, color=INK, loc='left')
    ax.set_xlim(-.5, max(depth.values()) + .5)
    ax.set_ylim(-1.5, 1.5)
    ax.axis('off')
fig.tight_layout()
fig.savefig(FIG / 'architectures.pdf')
