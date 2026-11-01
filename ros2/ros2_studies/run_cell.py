"""Estudio E1 a nivel de producción: seis celdas sin interfaz, primero sin fallas y luego con fallas continuas."""
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from common import CELL_MINUTES, CONFIGS, LAM, MTTR, NOMINAL_MINUTES, ORDER, REPLICATES, RESULTS, WARMUP, WINDOW
from configs import SINK, failing
from supervisor import System

CELL = Path(__file__).resolve().parent.parent / 'ros2_cell'


def start_cell(config, domain, port, log):
    env = {**os.environ, 'ROS_DOMAIN_ID': str(domain), 'ROS_LOCALHOST_ONLY': '1'}
    cell = subprocess.Popen([str(CELL / 'headless_cell.sh'), str(domain), str(port)], cwd=CELL, env=env,
                            stdout=subprocess.PIPE, text=True, start_new_session=True)
    if cell.stdout.readline().strip() != 'READY':
        raise RuntimeError('la celda no arrancó')
    topics = ','.join(f'/mtbf/out_{i}' for i in CONFIGS[config][SINK].inputs)
    ctrl = subprocess.Popen([sys.executable, str(CELL / 'line_controller.py'), '--heartbeat', topics], cwd=CELL, env=env,
                            stdout=log, stderr=log, start_new_session=True)
    return cell, ctrl


def stop_group(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    p.wait()


def inject(system, rng, seconds, faults, log):
    """Fallas y reparaciones continuas, sin reinicio entre pérdidas de función."""
    names = failing(system.config)
    t0 = time.monotonic()
    next_fail = {n: t0 + rng.exponential(1 / LAM) for n in names} if faults else {}
    next_spawn = {}
    while time.monotonic() - t0 < seconds:
        time.sleep(0.005)
        now = time.monotonic()
        for name, due in list(next_fail.items()):
            if now >= due:
                system.kill(name)
                del next_fail[name]
                next_spawn[name] = now + rng.exponential(MTTR)
        for name, due in list(next_spawn.items()):
            if now >= due:
                system.spawn(name)
                del next_spawn[name]
                next_fail[name] = now + 1.65 + rng.exponential(1 / LAM)
        if now - system.last_rx > 60:
            print(f'INCIDENTE {time.monotonic() - t0:.1f}', file=log, flush=True)
            return False
    return True


def run(config, name, index, phase, seed, minutes, faults, out):
    """Acumula el tiempo pedido; si un dominio se bloquea, sigue en otro y el análisis descarta la ventana afectada."""
    rng = np.random.default_rng(seed)
    remaining, attempt = minutes * 60 + WARMUP, 0
    while remaining > WINDOW:
        domain = 40 + 2 * index + 10 * attempt + (phase % 2)
        begin = time.monotonic()
        with open(out / f'cell_{phase}_{name}_a{attempt}.log', 'w') as log:
            cell, ctrl = start_cell(config, domain, 11400 + index + 20 * attempt, log)
            system = System(config, domain)
            system.start()
            try:
                if not system.wait_healthy(timeout=120):
                    print('INCIDENTE arranque', file=log, flush=True)
                    ok = False
                else:
                    ok = inject(system, rng, remaining, faults, log)
            finally:
                system.stop()
                stop_group(ctrl)
                stop_group(cell)
        if ok:
            return
        remaining -= time.monotonic() - begin
        remaining += WINDOW + WARMUP
        attempt += 1


def phase_all(phase, seed_base, minutes, faults, out):
    procs = [mp.Process(target=run, args=(c, c, i, phase, seed_base + i, minutes, faults, out)) for i, c in enumerate(ORDER)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    return [p.exitcode for p in procs]


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / 'run_cell.log', 'a')
    print(time.strftime('%H:%M:%S'), 'nominal', phase_all(0, 5000, NOMINAL_MINUTES * scale, False, out), file=log, flush=True)
    for r in range(1, REPLICATES + 1):
        print(time.strftime('%H:%M:%S'), 'replica', r, phase_all(r, 5000 + 100 * r, CELL_MINUTES * scale, True, out), file=log, flush=True)
    print(time.strftime('%H:%M:%S'), 'terminado', file=log, flush=True)


if __name__ == '__main__':
    main()
