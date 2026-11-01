"""Analiza E1, E2 y E3 con los criterios de PROTOCOL.md; escribe tablas en results/ y figuras en el manuscrito."""
import glob
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import BETA, CONFIGS, GROUPS, LAM, LOSS_CONFIGS, LOSSES, MTTR, ORDER, RESULTS as OUT, WARMUP, WINDOW
from predict import availability, mfpt

FIG = Path(__file__).resolve().parent.parent.parent / 'papers' / 'robotics_ros2' / 'figures'
RNG = np.random.default_rng(11)
INK, MUTED, GRID, COL_A, COL_B = '#0b0b0b', '#52514e', '#e4e3df', '#2a78d6', '#eb6834'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': MUTED, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})


def boot(x, n=10000):
    return RNG.choice(np.asarray(x, float), (n, len(x))).mean(axis=1)


def ci(b):
    return np.percentile(b, [2.5, 97.5])


def load(name):
    return pd.read_csv(OUT / f'{name}.csv')


lat = np.array(json.loads((OUT / 'latency.json').read_text()))
mu = 1 / (MTTR + lat.mean())
print(f'latencia n={len(lat)} media={lat.mean():.3f} sd={lat.std(ddof=1):.3f}')
incidents = {Path(f).name.split('.')[0]: len(json.loads(Path(f).read_text())) for f in glob.glob(str(OUT / '*.incidents.json'))}
print('incidentes', {k: v for k, v in incidents.items() if v} or 'ninguno')

# E1a
rows, boots = [], {}
for c in ORDER:
    d = load(f'E1_{c}')
    x = d.t_obs.to_numpy()
    b = boot(x)
    boots[c] = b
    lo, hi = ci(b)
    a, s = mfpt(CONFIGS[c], LAM, mu), mfpt(CONFIGS[c], LAM, mu, True)
    rows.append({'config': c, 'n': len(x), 'mean': x.mean(), 'lo': lo, 'hi': hi, 'A': a, 'err_A': 100 * (a - x.mean()) / x.mean(),
                 'A_in': lo <= a <= hi, 'C1': lo <= a <= hi or abs(a - x.mean()) / x.mean() <= .15, 'B': s,
                 'err_B': 100 * (s - x.mean()) / x.mean(), 'B_in': lo <= s <= hi, 'spur': 100 * d.t_logical.isna().mean(),
                 'cens': int(d.censored.sum()), 'gap2': int(((d.t_obs - d.t_logical) > 2).sum())})
e1 = pd.DataFrame(rows)
e1.to_csv(OUT / 'E1a_summary.csv', index=False)
pd.set_option('display.width', 220, 'display.max_columns', None)
print('E1a\n', e1.round(2).to_string(index=False))
hyp = []
for h, c in (('H1', 'd_parallel'), ('H2', 'd_triangle')):
    diff = boots[c] - boots['d_series']
    hyp.append({'h': h, 'diff': e1.set_index('config').loc[c, 'mean'] - e1.set_index('config').loc['d_series', 'mean'], 'lo': ci(diff)[0], 'hi': ci(diff)[1]})
print(pd.DataFrame(hyp).round(2).to_string(index=False))
pd.DataFrame(hyp).to_csv(OUT / 'E1a_hypotheses.csv', index=False)

# E2
rows = []
for c, g in GROUPS.items():
    d = load(f'E2_{c}')
    x = d.t_obs.to_numpy()
    lo, hi = ci(boot(x))
    a, cc = mfpt(CONFIGS[c], LAM, mu), mfpt(CONFIGS[c], LAM, mu, groups=g, beta=BETA)
    rows.append({'config': c, 'n': len(x), 'mean': x.mean(), 'lo': lo, 'hi': hi, 'A': a, 'A_in': lo <= a <= hi, 'err_A': 100 * (a - x.mean()) / x.mean(),
                 'CC': cc, 'CC_in': lo <= cc <= hi, 'err_CC': 100 * (cc - x.mean()) / x.mean(),
                 'C6': lo <= cc <= hi or abs(cc - x.mean()) / x.mean() <= .15, 'spur': 100 * d.t_logical.isna().mean()})
e2 = pd.DataFrame(rows)
e2.to_csv(OUT / 'E2_summary.csv', index=False)
print('E2\n', e2.round(2).to_string(index=False))

# E3
rows, sp = [], {}
for p in LOSSES:
    for c in LOSS_CONFIGS:
        d = load(f'E3_{c}_p{int(p * 100)}')
        x = d.t_obs.to_numpy()
        lo, hi = ci(boot(x))
        a = mfpt(CONFIGS[c], LAM, mu)
        sp[(c, p)] = d.t_logical.isna().to_numpy(float)
        rows.append({'config': c, 'p': p, 'n': len(x), 'mean': x.mean(), 'lo': lo, 'hi': hi, 'A': a, 'err_A': 100 * (a - x.mean()) / x.mean(),
                     'C1': lo <= a <= hi or abs(a - x.mean()) / x.mean() <= .15, 'spur': 100 * sp[(c, p)].mean()})
e3 = pd.DataFrame(rows)
e3.to_csv(OUT / 'E3_summary.csv', index=False)
print('E3\n', e3.round(2).to_string(index=False))
h3 = boot(sp[('d_series', .3)]) - boot(sp[('d_parallel', .3)])
print('H3 espurias d_series - d_parallel a p=.3: dif', round(100 * (sp[('d_series', .3)].mean() - sp[('d_parallel', .3)].mean()), 1), 'IC', (100 * ci(h3)).round(1))
pd.DataFrame([{'diff': 100 * (sp[('d_series', .3)].mean() - sp[('d_parallel', .3)].mean()), 'lo': 100 * ci(h3)[0], 'hi': 100 * ci(h3)[1]}]).to_csv(OUT / 'E3_h3.csv', index=False)


# E1b
def parse(path):
    times, up, last = [], [], 0.0
    incident = None
    for line in Path(path).read_text().splitlines():
        m = re.match(r'(\d+\.\d+) (.*)', line)
        if line.startswith('INCIDENTE'):
            incident = True
            continue
        if not m:
            continue
        t, text = float(m.group(1)), m.group(2)
        last = t
        if text.startswith('deja '):
            times.append(t)
        elif text in ('MARCHA', 'PARO'):
            up.append((t, text == 'MARCHA'))
    return np.array(times), up, last, incident


def windows(path):
    times, up, last, incident = parse(path)
    marchas = [t for t, s in up if s]
    if not marchas:
        return []
    start = marchas[0] + WARMUP
    end = last - 60 if incident else last
    out, k = [], 0
    while start + (k + 1) * WINDOW <= end:
        a, b = start + k * WINDOW, start + (k + 1) * WINDOW
        rate = ((times >= a) & (times < b)).sum() * 3600 / WINDOW
        edges = [a] + [t for t, _ in up if a < t < b] + [b]
        state = [s for t, s in up if t <= a][-1]
        on = 0.0
        ev = [(t, s) for t, s in up if a < t < b]
        cursor = a
        for t, s in ev:
            if state:
                on += t - cursor
            cursor, state = t, s
        if state:
            on += b - cursor
        out.append((rate, on / WINDOW))
        k += 1
    return out


nominal = []
for c in ORDER:
    for f in glob.glob(str(OUT / f'cell_0_{c}_a*.log')):
        times, up, last, incident = parse(f)
        marchas = [t for t, s in up if s]
        if len(marchas) and not incident:
            t = times[times >= marchas[0] + WARMUP]
            nominal.append(len(t) * 3600 / (last - marchas[0] - WARMUP))
R0 = float(np.mean(nominal))
print('R0 cajas/h', round(R0, 1), np.round(nominal, 1))
rows, wins = [], {}
for c in ORDER:
    w = [x for f in sorted(glob.glob(str(OUT / f'cell_[123]_{c}_a*.log'))) for x in windows(f)]
    wins[c] = np.array(w)
    rate, av = wins[c][:, 0], wins[c][:, 1]
    lo, hi = ci(boot(rate))
    aa, ab = availability(CONFIGS[c], LAM, mu), availability(CONFIGS[c], LAM, mu, True)
    pa, pb = R0 * aa, R0 * ab
    rows.append({'config': c, 'windows': len(rate), 'rate': rate.mean(), 'lo': lo, 'hi': hi, 'pred_A': pa, 'err_A': 100 * (pa - rate.mean()) / rate.mean(),
                 'A_in': lo <= pa <= hi, 'C3': lo <= pa <= hi or abs(pa - rate.mean()) / rate.mean() <= .15, 'pred_B': pb,
                 'err_B': 100 * (pb - rate.mean()) / rate.mean(), 'B_in': lo <= pb <= hi, 'avail_obs': av.mean(), 'avail_A': aa, 'avail_B': ab})
e1b = pd.DataFrame(rows)
e1b.to_csv(OUT / 'E1b_summary.csv', index=False)
print('E1b\n', e1b.round(3).to_string(index=False))

# figuras
fig, ax = plt.subplots(figsize=(6.3, 2.7))
for i, row in enumerate(e1b.iloc[::-1].itertuples()):
    ax.plot([row.lo, row.hi], [i, i], color=MUTED, lw=2, solid_capstyle='round', zorder=1)
    ax.scatter(row.rate, i, s=36, color=INK, zorder=3, label='Observed, 95% CI' if i == 0 else None)
    ax.scatter(row.pred_B, i, s=46, marker='s', color=COL_B, edgecolor='#fcfcfb', lw=.8, zorder=4, label='B: links in series' if i == 0 else None)
    ax.scatter(row.pred_A, i, s=46, marker='D', color=COL_A, edgecolor='#fcfcfb', lw=.8, zorder=5, label='A: graph logic' if i == 0 else None)
ax.set_yticks(range(6), list(e1b.config[::-1]), family='monospace')
ax.set_xlabel('Production (boxes per hour)')
ax.grid(axis='x', color=GRID, lw=.6)
ax.set_axisbelow(True)
ax.tick_params(length=0)
h, l = ax.get_legend_handles_labels()
fig.legend(h, l, frameon=False, ncol=3, loc='upper center', labelcolor=MUTED)
fig.tight_layout(rect=(0, 0, 1, .92))
fig.savefig(FIG / 'production.pdf')

fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.5))
for c, mark, col in zip(LOSS_CONFIGS, ('o', 'D', 's'), ('#2a78d6', '#eb6834', '#1baf7a')):
    g = e3[e3.config == c]
    axes[0].errorbar([0, *g.p], [e1.set_index('config').loc[c, 'mean'], *g['mean']],
                     yerr=[[e1.set_index('config').loc[c, 'mean'] - e1.set_index('config').loc[c, 'lo'], *(g['mean'] - g.lo)],
                           [e1.set_index('config').loc[c, 'hi'] - e1.set_index('config').loc[c, 'mean'], *(g.hi - g['mean'])]],
                     marker=mark, ms=5, color=col, lw=1.5, capsize=2, label=c)
    axes[1].plot(g.p, g.spur, marker=mark, ms=5, color=col, lw=2, label=c)
axes[0].set_xlabel('Message loss p')
axes[0].set_ylabel('Mean time to loss (s)')
axes[1].set_xlabel('Message loss p')
axes[1].set_ylabel('Spurious losses (%)')
axes[1].axhline(5, color=MUTED, lw=.8, ls=':')
for ax in axes:
    ax.grid(color=GRID, lw=.5)
    ax.set_axisbelow(True)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, ncol=3, loc='upper center', labelcolor=MUTED, prop={'family': 'monospace'})
fig.tight_layout(rect=(0, 0, 1, .9))
fig.savefig(FIG / 'message_loss.pdf')
