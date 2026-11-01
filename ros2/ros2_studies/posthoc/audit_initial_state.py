"""Auditoría posterior al congelamiento: al empezar cada intento, ¿todos los componentes están publicando?"""
import csv
import json
import multiprocessing as mp
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ORDER  # noqa: E402
from configs import failing  # noqa: E402
from run_signal import LossySystem, run_trial  # noqa: E402

N, FRESH = int(sys.argv[1]) if len(sys.argv) > 1 else 30, 0.5


def worker(config, index):
    system = LossySystem(config, 70 + index, 0.0)
    names = failing(system.config)
    probe = subprocess.Popen([sys.executable, str(HERE / 'probe.py'), ','.join(names)], env=system.env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    last, pending, delay, lock = {}, {}, {}, threading.Lock()

    def read():
        for line in probe.stdout:
            name, t = line.split()
            with lock:
                last[name] = float(t)
                if name in pending:
                    delay[name] = float(t) - pending.pop(name)
    threading.Thread(target=read, daemon=True).start()
    rng = np.random.default_rng(7000 + index)
    system.start()
    try:
        with open(HERE / 'results' / f'initial_{config}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, ['config', 'trial', 'stale', 'delays', 't_obs'])
            w.writeheader()
            for trial in range(N):
                if not system.wait_healthy(timeout=90):
                    print('INCIDENTE', config, trial, file=sys.stderr, flush=True)
                    return
                now = time.monotonic()
                with lock:
                    stale = [n for n in names if now - last.get(n, 0) > FRESH]
                    delay.clear()
                    pending.clear()
                    pending.update({n: now for n in stale})
                row = run_trial(system, rng, (), 0.0)
                with lock:
                    w.writerow({'config': config, 'trial': trial, 'stale': ';'.join(stale), 'delays': json.dumps(delay), 't_obs': row['t_obs']})
                f.flush()
                system.respawn_missing()
    finally:
        system.stop()
        subprocess.run(['kill', '-9', str(probe.pid)])


if __name__ == '__main__':
    procs = [mp.Process(target=worker, args=(c, i)) for i, c in enumerate(ORDER)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
