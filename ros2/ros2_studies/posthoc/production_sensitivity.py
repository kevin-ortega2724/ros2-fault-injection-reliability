"""Análisis posteriores al congelamiento de E1b: conteo de tiempo, incidentes, réplicas y dependencia entre ventanas."""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

from common import CONFIGS, LAM, MTTR, ORDER, WARMUP, WINDOW
from predict import availability

RES = ROOT / 'results'
OUT = HERE / 'results'
rng = np.random.default_rng(31)
lat = np.array(json.loads((RES / 'latency.json').read_text()))
mu = 1 / (MTTR + lat.mean())
e1b = pd.read_csv(RES / 'E1b_summary.csv').set_index('config')
R0 = e1b.pred_A / e1b.avail_A


def parse(path):
    boxes, up, last, inc = [], [], 0.0, None
    for line in Path(path).read_text().splitlines():
        if line.startswith('INCIDENTE'):
            inc = line.split()[1]
            continue
        m = re.match(r'(\d+\.\d+) (.*)', line)
        if m:
            last = float(m[1])
            if m[2].startswith('deja '):
                boxes.append(last)
            elif m[2] in ('MARCHA', 'PARO'):
                up.append((last, m[2] == 'MARCHA'))
    return np.array(boxes), up, last, inc


def on_time(up, a, b):
    state = [s for t, s in up if t <= a]
    state, cur, on = (state[-1] if state else False), a, 0.0
    for t, s in up:
        if a < t < b:
            on += (t - cur) if state else 0
            cur, state = t, s
    return on + ((b - cur) if state else 0)


acc, windows, stops = [], [], []
for c in ORDER:
    for r in (1, 2, 3):
        for f in sorted(glob.glob(str(RES / f'cell_{r}_{c}_a*.log'))):
            boxes, up, last, inc = parse(f)
            attempt = int(f.rsplit('_a', 1)[1][0])
            marchas = [t for t, s in up if s]
            first = marchas[0]
            start = first + WARMUP
            # fin real: la hora del incidente usa el reloj del inyector, que arranca antes; se aproxima con el último evento + 60 s
            end_obs = last + 60 if inc else last
            end_use = last - 60 if inc else last
            k = 0
            while start + (k + 1) * WINDOW <= end_use:
                a = start + k * WINDOW
                b = a + WINDOW
                windows.append({'config': c, 'rep': r, 'attempt': attempt, 'k': k, 'rate': ((boxes >= a) & (boxes < b)).sum() * 3600 / WINDOW})
                k += 1
            used = k * WINDOW
            acc.append({'config': c, 'rep': r, 'attempt': attempt, 'incident': bool(inc), 'observed': end_obs - first, 'warmup': WARMUP, 'used': used,
                        'excluded': end_obs - first - WARMUP - used, 'boxes_after_warmup': int((boxes >= start).sum()), 'seconds_after_warmup': end_obs - start})
            ev = [(t, s) for t, s in up if t >= start]
            downs = [(ev[i + 1][0] - ev[i][0]) for i in range(len(ev) - 1) if not ev[i][1] and ev[i + 1][1]]
            n_stops = sum(not s for _, s in ev)
            stops.append({'config': c, 'seconds': end_use - start, 'stops': n_stops, 'down': sum(downs), 'n_closed': len(downs)})
acc, win = pd.DataFrame(acc), pd.DataFrame(windows)
acc.to_csv(OUT / 'E1b_time_accounting.csv', index=False)
win.to_csv(OUT / 'E1b_windows.csv', index=False)

rows = []
for c in ORDER:
    a, w = acc[acc.config == c], win[win.config == c]
    rep = w.groupby('rep').rate.mean()
    # bootstrap por bloques móviles de 3 ventanas dentro de cada ejecución continua
    series = [g.sort_values('k').rate.to_numpy() for _, g in w.groupby(['rep', 'attempt'])]
    blocks = [s[i:i + 3] for s in series for i in range(max(len(s) - 2, 1))]
    n, boots = len(w), []
    for _ in range(10000):
        out = []
        while len(out) < n:
            out.extend(blocks[rng.integers(len(blocks))])
        boots.append(np.mean(out[:n]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    # t con df=2 sobre medias de réplica
    se = rep.std(ddof=1) / np.sqrt(3)
    tlo, thi = rep.mean() - 4.303 * se, rep.mean() + 4.303 * se
    x = w.sort_values(['rep', 'attempt', 'k'])
    pairs = [(g.rate.values[:-1], g.rate.values[1:]) for _, g in x.groupby(['rep', 'attempt']) if len(g) > 2]
    r1 = np.corrcoef(np.concatenate([p[0] for p in pairs]), np.concatenate([p[1] for p in pairs]))[0, 1]
    pa, pb = e1b.pred_A[c], e1b.pred_B[c]
    eff = a.boxes_after_warmup.sum() * 3600 / a.seconds_after_warmup.sum()
    inc = int(a.incident.sum())
    s = [x for x in stops if x['config'] == c]
    rows.append({'config': c, 'rep1': rep[1], 'rep2': rep[2], 'rep3': rep[3], 'lag1': r1, 'block_lo': lo, 'block_hi': hi, 'A_in_block': lo <= pa <= hi, 'B_in_block': lo <= pb <= hi,
                 't_lo': tlo, 't_hi': thi, 'A_in_t': tlo <= pa <= thi, 'B_in_t': tlo <= pb <= thi, 'C3_block': lo <= pa <= hi or abs(pa - w.rate.mean()) / w.rate.mean() <= .15,
                 'rate_protocol': w.rate.mean(), 'rate_effective': eff, 'err_A_eff': 100 * (pa - eff) / eff, 'err_B_eff': 100 * (pb - eff) / eff, 'incidents': inc,
                 'observed_s': a.observed.sum(), 'warmup_s': a.warmup.sum(), 'used_s': a.used.sum(), 'excluded_s': a.excluded.sum(), 'attempts': len(a), 'windows': len(w),
                 'stops_per_300s': 300 * sum(x['stops'] for x in s) / sum(x['seconds'] for x in s), 'mean_stop_s': sum(x['down'] for x in s) / max(sum(x['n_closed'] for x in s), 1)})
t = pd.DataFrame(rows)
t.to_csv(OUT / 'E1b_sensitivity.csv', index=False)
pd.set_option('display.width', 250, 'display.max_columns', None)
print(t.round(2).T.to_string())
print('R0 unico', R0.round(3).unique())
