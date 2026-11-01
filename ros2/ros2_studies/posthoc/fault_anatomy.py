"""Corrida ilustrativa posterior al congelamiento: la misma falla, un enlace, en d_series y d_parallel, con el instante de cada SIGKILL."""
import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import CONFIGS  # noqa: E402
from configs import SINK  # noqa: E402
from run_cell import CELL, stop_group  # noqa: E402
from supervisor import System  # noqa: E402

CASES = {'d_series': 'l12', 'd_parallel': 'la'}
N, DOWN, WARM = int(sys.argv[1]) if len(sys.argv) > 1 else 20, 4.0, 60.0


def run(config, victim, index):
    domain, port = 81 + 2 * index, 11490 + index
    rng = np.random.default_rng(9000 + index)
    env = {**System(config, domain).env}
    cell = subprocess.Popen([str(CELL / 'headless_cell.sh'), str(domain), str(port)], cwd=CELL, env=env,
                            stdout=subprocess.PIPE, text=True, start_new_session=True)
    if cell.stdout.readline().strip() != 'READY':
        raise RuntimeError('la celda no arrancó')
    topics = ','.join(f'/mtbf/out_{i}' for i in CONFIGS[config][SINK].inputs)
    out = HERE / 'results' / f'anatomy_{config}'
    with open(f'{out}.ctrl.log', 'w') as log, open(f'{out}.faults.log', 'w') as faults:
        ctrl = subprocess.Popen([sys.executable, str(HERE / 'anatomy_controller.py'), '--heartbeat', topics], cwd=CELL, env=env,
                                stdout=log, stderr=subprocess.DEVNULL, start_new_session=True)
        system = System(config, domain)
        system.start()
        try:
            if not system.wait_healthy(timeout=120):
                raise RuntimeError('sin señal')
            time.sleep(WARM)
            for _ in range(N):
                system.kill(victim)
                print(f'{time.monotonic():.4f} kill {victim}', file=faults, flush=True)
                time.sleep(DOWN)
                system.spawn(victim)
                print(f'{time.monotonic():.4f} spawn {victim}', file=faults, flush=True)
                time.sleep(rng.uniform(20.0, 25.0))
        finally:
            system.stop()
            stop_group(ctrl)
            stop_group(cell)


if __name__ == '__main__':
    procs = [mp.Process(target=run, args=(c, v, i)) for i, (c, v) in enumerate(CASES.items())]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    print('códigos', [p.exitcode for p in procs])
