"""Comprobaciones posteriores al congelamiento: forma de la reparación y relación entre pérdida lógica y observada."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

from common import CONFIGS, DEADLINE, LAM, MTTR, ORDER
from configs import failing, function_up
from predict import mfpt

lat = np.array(json.loads((ROOT / 'results' / 'latency.json').read_text()))
mu = 1 / (MTTR + lat.mean())
rng = np.random.default_rng(41)
rows = []
for c in ORDER:
    cfg = CONFIGS[c]
    names = failing(cfg)
    out, out_th = [], []
    for sim, (store, th) in enumerate(((out, 0.0), (out_th, DEADLINE))):
        for _ in range(20000):
            t, fail, rep, lost = 0.0, {n: rng.exponential(1 / LAM) for n in names}, {}, None
            while True:
                times = {**fail, **rep}
                n = min(times, key=times.get)
                t = times[n]
                if lost is not None and t >= lost + th:
                    store.append(lost)
                    break
                if n in fail:
                    del fail[n]
                    rep[n] = t + rng.exponential(MTTR) + rng.choice(lat)
                else:
                    del rep[n]
                    fail[n] = t + rng.exponential(1 / LAM)
                up = function_up(cfg, {m: m in fail for m in names})
                if not up and lost is None:
                    lost = t
                    if th == 0.0:
                        store.append(lost)
                        break
                elif up:
                    lost = None
    d = pd.read_csv(ROOT / 'results' / f'E1_{c}.csv')
    gap = (d.t_logical - d.t_obs).dropna()
    a = mfpt(cfg, LAM, mu)
    rows.append({'config': c, 'A_exp': a, 'A_real_repair': np.mean(out), 'se': np.std(out) / np.sqrt(len(out)), 'diff_pct': 100 * (np.mean(out) - a) / a, 'A_threshold': np.mean(out_th), 'se_th': np.std(out_th) / np.sqrt(len(out_th)), 'obs': d.t_obs.mean(),
                 'err_th': 100 * (np.mean(out_th) - d.t_obs.mean()) / d.t_obs.mean(),
                 'n_logical': len(gap), 'gap_median': gap.median(), 'gap_p05': gap.quantile(.05), 'gap_p95': gap.quantile(.95), 'obs_after_2s': int((-gap > 2).sum()), 'mean_shift': (d.t_obs - d.t_logical).mean()})
t = pd.DataFrame(rows)
t.to_csv(HERE / 'results' / 'model_checks.csv', index=False)
pd.set_option('display.width', 250, 'display.max_columns', None)
print(t.round(3).to_string())
print('L min p1 p5 p50 p95 >2s', lat.min().round(3), np.percentile(lat, [1, 5, 50, 95]).round(3), (lat > 2).mean().round(4))
