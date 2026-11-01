"""Definiciones compartidas de los estudios E1, E2 y E3; los valores están fijados en PROTOCOL.md."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'ros2_pilot'))

from configs import CONFIGS  # noqa: E402

RESULTS = HERE / 'results'
LAM, MTTR, DEADLINE = 1 / 60, 4.0, 0.5
LATENCY_FOR_LOGICAL = 1.65
BETA = 0.2
GROUPS = {'d_parallel': (('la', 'lb'),), 'r2oo3': (('c1', 'c2', 'c3'),),
          'cen': (('s1', 's2'), ('a1', 'a2')), 'd_units': (('p1', 'p2', 'p3'),)}
LOSSES = (0.1, 0.2, 0.3)
LOSS_CONFIGS = ('d_series', 'd_parallel', 'r2oo3')
N_E1, N_E2, N_E3 = 160, 100, 60
ORDER = ['d_series', 'd_parallel', 'd_triangle', 'd_units', 'r2oo3', 'cen']
WINDOW, WARMUP, CELL_MINUTES, REPLICATES, NOMINAL_MINUTES = 300.0, 60.0, 40.0, 3, 10.0


def tasks():
    out = [{'study': 'E1', 'config': c, 'beta': 0.0, 'loss': 0.0, 'n': N_E1} for c in ORDER]
    out += [{'study': 'E2', 'config': c, 'beta': BETA, 'loss': 0.0, 'n': N_E2} for c in GROUPS]
    out += [{'study': 'E3', 'config': c, 'beta': 0.0, 'loss': p, 'n': N_E3} for p in LOSSES for c in LOSS_CONFIGS]
    return out


def task_name(t):
    return f"{t['study']}_{t['config']}" + (f"_p{int(t['loss'] * 100)}" if t['loss'] else '')


if __name__ == '__main__':
    import json

    from predict import availability, mfpt
    lat = 1.674
    mu = 1 / (MTTR + lat)
    print('E2 con L=1.674 (referencia)')
    for c, g in GROUPS.items():
        print(c, 'A', round(mfpt(CONFIGS[c], LAM, mu), 2), 'A+ccf', round(mfpt(CONFIGS[c], LAM, mu, groups=g, beta=BETA), 2))
    print('Disponibilidad')
    for c in ORDER:
        print(c, round(availability(CONFIGS[c], LAM, mu), 4), round(availability(CONFIGS[c], LAM, mu, True), 4))
    print(len(tasks()), json.dumps([task_name(t) for t in tasks()]))
