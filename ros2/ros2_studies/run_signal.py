"""Estudios E1 (señal), E2 y E3: primer paso con inyección, un proceso por componente y filas válidas únicamente."""
import csv
import json
import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from common import CONFIGS, DEADLINE, GROUPS, LAM, LATENCY_FOR_LOGICAL, MTTR, RESULTS, task_name, tasks
from configs import failing, function_up
from supervisor import System, calibrate_latency

FIELDS = ['study', 'config', 'beta', 'loss', 'trial', 't_obs', 't_logical', 'kills', 'spawns', 'censored', 'domain']


class LossySystem(System):
    def __init__(self, config_name, domain, loss):
        super().__init__(config_name, domain)
        self.loss = loss

    def _cmd(self, name, role):
        cmd = super()._cmd(name, role)
        return cmd + ['--loss', str(self.loss)] if role == 'relay' and self.loss else cmd


def run_trial(system, rng, groups, beta, max_seconds=1800.0):
    names = failing(system.config)
    member = {n: g for g in groups for n in g}
    t0 = time.monotonic()
    next_fail = {n: t0 + rng.exponential(1 / LAM) for n in names}
    next_spawn, up_at = {}, {}
    kills = spawns = 0
    t_logical = None

    def fail(name, now):
        nonlocal kills
        system.kill(name)
        kills += 1
        del next_fail[name]
        next_spawn[name] = now + rng.exponential(MTTR)

    while True:
        time.sleep(0.005)
        now = time.monotonic()
        for name, due in list(next_fail.items()):
            if name in next_fail and now >= due:
                if name in member and rng.random() < beta:
                    for other in member[name]:
                        if other in next_fail:
                            fail(other, now)
                else:
                    fail(name, now)
        for name, due in list(next_spawn.items()):
            if now >= due:
                system.spawn(name)
                spawns += 1
                del next_spawn[name]
                up_at[name] = now + LATENCY_FOR_LOGICAL
        for name, due in list(up_at.items()):
            if now >= due:
                del up_at[name]
                next_fail[name] = now + rng.exponential(1 / LAM)
        up = {n: n in next_fail for n in names}
        if t_logical is None and not function_up(system.config, up):
            t_logical = now - t0
        last = system.last_rx
        if now - last > DEADLINE:
            return {'t_obs': max(last - t0, 0.0), 't_logical': t_logical, 'kills': kills, 'spawns': spawns, 'censored': False}
        if now - t0 > max_seconds:
            return {'t_obs': now - t0, 't_logical': t_logical, 'kills': kills, 'spawns': spawns, 'censored': True}


def restored_system(config, domain, loss, incidents):
    """Un dominio que no recupera señal no se reutiliza; los intentos solo se miden con señal estable."""
    for _ in range(4):
        system = LossySystem(config, domain, loss)
        system.start()
        if system.wait_healthy(timeout=90):
            return system, domain
        incidents.append({'domain': domain, 'time': time.strftime('%H:%M:%S')})
        system.stop()
        domain += 1
    raise RuntimeError('sin señal en cuatro dominios')


def worker(task, index, out, n_override):
    n = n_override or task['n']
    rng = np.random.default_rng(3000 + index)
    groups = GROUPS.get(task['config'], ()) if task['beta'] else ()
    incidents = []
    name = task_name(task)
    domain = 20 + 3 * index
    if domain >= 30:
        domain += 3
    system, domain = restored_system(task['config'], domain, task['loss'], incidents)
    try:
        with open(out / f'{name}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            for trial in range(n):
                row = run_trial(system, rng, groups, task['beta'])
                w.writerow({'study': task['study'], 'config': task['config'], 'beta': task['beta'], 'loss': task['loss'],
                            'trial': trial, 'domain': domain, **row})
                f.flush()
                system.respawn_missing()
                if not system.wait_healthy():
                    incidents.append({'domain': domain, 'after_trial': trial})
                    system.stop()
                    system, domain = restored_system(task['config'], domain + 1, task['loss'], incidents)
    finally:
        system.stop()
        (out / f'{name}.incidents.json').write_text(json.dumps(incidents, indent=1))


def calibration(path):
    values = []
    while True:
        values.extend(calibrate_latency(domain=95, n=20, seed=len(values)).tolist())
        Path(path).write_text(json.dumps(values))


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS
    n_override = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
    out.mkdir(parents=True, exist_ok=True)
    calib = mp.Process(target=calibration, args=(out / 'latency.json',), daemon=True)
    calib.start()
    pending = [(i, t) for i, t in enumerate(tasks()) if not only or task_name(t) in only]
    running = {}
    log = open(out / 'run_signal.log', 'a')
    while pending or running:
        for i, p in list(running.items()):
            if not p.is_alive():
                print(time.strftime('%H:%M:%S'), 'fin', i, p.exitcode, file=log, flush=True)
                del running[i]
        while pending and len(running) < 6:
            i, t = pending.pop(0)
            p = mp.Process(target=worker, args=(t, i, out, n_override))
            p.start()
            running[i] = p
            print(time.strftime('%H:%M:%S'), 'inicio', i, task_name(t), file=log, flush=True)
        time.sleep(2)
    calib.terminate()
    calib.join()
    subprocess.run(['pkill', '-9', '-f', 'ros2_pilot/component.py'])
    print(time.strftime('%H:%M:%S'), 'terminado', file=log, flush=True)


if __name__ == '__main__':
    main()
