"""Completa los intentos válidos de cen según DEVIATIONS.md; nunca mide sin señal restablecida."""
import csv
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np

from run_pilot import DEADLINE, LAM, LATENCY_FOR_LOGICAL, MTTR, N, calibration
from supervisor import System, run_trial

OUT = Path(__file__).resolve().parent / 'results'
FIELDS = ['config', 'trial', 't_obs', 't_logical', 'kills', 'spawns', 'censored', 'restored']


def restore(domain):
    """Arranca en un dominio nuevo hasta recuperar señal; un dominio bloqueado no se reutiliza."""
    for _ in range(3):
        system = System('cen', domain)
        system.start()
        if system.wait_healthy(timeout=120):
            return system, domain
        system.stop()
        domain += 1
    raise RuntimeError('sin señal en tres dominios')


def main():
    with open(OUT / 'trials_cen.csv', newline='') as f:
        done = len(list(csv.DictReader(f)))
    rng = np.random.default_rng(2000)
    calib = mp.Process(target=calibration, args=(OUT / 'latency_resume.json',), daemon=True)
    calib.start()
    system, domain = restore(16)
    incidents = 0
    try:
        with open(OUT / 'trials_cen.csv', 'a', newline='') as f:
            w = csv.DictWriter(f, FIELDS)
            for trial in range(done, N):
                row = run_trial(system, rng, LAM, MTTR, LATENCY_FOR_LOGICAL, DEADLINE)
                w.writerow({'config': 'cen', 'trial': trial, 'restored': True, **row})
                f.flush()
                system.respawn_missing()
                if not system.wait_healthy():
                    incidents += 1
                    system.stop()
                    system, domain = restore(domain + 1)
    finally:
        system.stop()
        calib.terminate()
    (OUT / 'resume_meta.json').write_text(json.dumps(
        {'finished': time.strftime('%Y-%m-%dT%H:%M:%S'), 'seed': 2000, 'incidents': incidents,
         'last_domain': domain}, indent=1))


if __name__ == '__main__':
    main()
