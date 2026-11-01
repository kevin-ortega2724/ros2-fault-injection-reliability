"""Compara tiempos observados con las predicciones A y B según PROTOCOL.md."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from configs import CONFIGS
from predict import mfpt

OUT = Path(__file__).resolve().parent / 'results'
LAM, MTTR = 1 / 60, 4.0
RNG = np.random.default_rng(7)


def boot_mean(x, n=10000):
    return RNG.choice(x, (n, len(x))).mean(axis=1)


lat = np.array(json.loads((OUT / 'latency.json').read_text()))
mu = 1 / (MTTR + lat.mean())
print(f'latencia: n={len(lat)} media={lat.mean():.3f} sd={lat.std(ddof=1):.3f} p95={np.percentile(lat, 95):.3f}')
rows, boots = [], {}
for name, cfg in CONFIGS.items():
    d = pd.read_csv(OUT / f'trials_{name}.csv')
    x = d.t_obs.to_numpy()
    b = boot_mean(x)
    boots[name] = b
    lo, hi = np.percentile(b, [2.5, 97.5])
    a, bb = mfpt(cfg, LAM, mu), mfpt(cfg, LAM, mu, True)
    rows.append({'config': name, 'n': len(x), 'obs_mean': x.mean(), 'ci_lo': lo, 'ci_hi': hi,
                 'pred_A': a, 'err_A_pct': 100 * (a - x.mean()) / x.mean(), 'A_in_ci': lo <= a <= hi,
                 'pred_B': bb, 'err_B_pct': 100 * (bb - x.mean()) / x.mean(), 'B_in_ci': lo <= bb <= hi,
                 'C1_A_ok': lo <= a <= hi or abs(a - x.mean()) / x.mean() <= 0.15,
                 'spurious_pct': 100 * d.t_logical.isna().mean(), 'censored': int(d.censored.sum()),
                 'logical_mean': d.t_logical.mean(), 'not_restored': int((~d.restored).sum())})
table = pd.DataFrame(rows)
table.to_csv(OUT / 'summary.csv', index=False)
pd.set_option('display.width', 220, 'display.max_columns', None)
print(table.round(2).to_string(index=False))
for h, c in (('H1', 'd_parallel'), ('H2', 'd_triangle')):
    diff = boots[c] - boots['d_series']
    print(h, c, '- d_series: media', round(diff.mean(), 2), 'IC95', np.percentile(diff, [2.5, 97.5]).round(2))
