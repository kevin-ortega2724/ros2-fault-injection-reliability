"""Ejecuta el piloto: una falla de sistema por fila en results/trials.csv."""
import csv
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

from configs import CONFIGS
from supervisor import System, calibrate_latency, run_trial

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
LAM, MTTR, DEADLINE, N = 1 / 60, 4.0, 0.5, 60
LATENCY_FOR_LOGICAL = 1.65  # calibración previa; solo sitúa el "operativo" lógico durante la corrida


def worker(name, index, n, path):
    rng = np.random.default_rng(1000 + index)
    system = System(name, 10 + index)
    system.start()
    try:
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, ['config', 'trial', 't_obs', 't_logical', 'kills', 'spawns', 'censored', 'restored'])
            w.writeheader()
            restored = system.wait_healthy(timeout=120)
            for trial in range(n):
                row = run_trial(system, rng, LAM, MTTR, LATENCY_FOR_LOGICAL, DEADLINE)
                w.writerow({'config': name, 'trial': trial, 'restored': restored, **row})
                f.flush()
                system.respawn_missing()
                restored = system.wait_healthy()
                if not restored:
                    system.stop()
                    system = System(name, 10 + index)
                    system.start()
                    restored = system.wait_healthy(timeout=120)
    finally:
        system.stop()


def calibration(path):
    values = []
    while True:
        values.extend(calibrate_latency(domain=90, n=20, seed=len(values)).tolist())
        Path(path).write_text(json.dumps(values))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N
    OUT.mkdir(exist_ok=True)
    meta = {'started': time.strftime('%Y-%m-%dT%H:%M:%S'), 'n': n,
            'protocol_sha256': hashlib.sha256((HERE / 'PROTOCOL.md').read_bytes()).hexdigest()}
    (OUT / 'meta.json').write_text(json.dumps(meta, indent=1))
    calib = mp.Process(target=calibration, args=(OUT / 'latency.json',), daemon=True)
    calib.start()
    procs = [mp.Process(target=worker, args=(c, i, n, OUT / f'trials_{c}.csv'))
             for i, c in enumerate(CONFIGS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    calib.terminate()
    meta['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    meta['exit_codes'] = [p.exitcode for p in procs]
    (OUT / 'meta.json').write_text(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()
