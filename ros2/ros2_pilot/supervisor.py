"""Inyección de fallas: mata y reinicia procesos ROS 2 y mide el primer paso a la pérdida de función."""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

from configs import CONFIGS, SINK, SOURCE, failing, function_up

HERE = Path(__file__).resolve().parent


class System:
    def __init__(self, config_name, domain):
        self.config = CONFIGS[config_name]
        self.env = {**os.environ, 'ROS_DOMAIN_ID': str(domain), 'ROS_LOCALHOST_ONLY': '1'}
        self.procs = {}
        self.last_rx = 0.0

    def _cmd(self, name, role):
        comp = self.config.get(name)
        inputs = ','.join(comp.inputs) if comp else ''
        k = comp.k if comp else 1
        return [sys.executable, str(HERE / 'component.py'), '--name', name, '--role', role,
                '--inputs', inputs, '--k', str(k)]

    def spawn(self, name):
        self.procs[name] = subprocess.Popen(self._cmd(name, 'relay'), env=self.env,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            start_new_session=True)

    def kill(self, name):
        proc = self.procs.pop(name)
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()

    def start(self):
        self.procs[SOURCE] = subprocess.Popen(self._cmd(SOURCE, 'source'), env=self.env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                              start_new_session=True)
        sink = subprocess.Popen(self._cmd(SINK, 'sink'), env=self.env, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        self.procs[SINK] = sink
        threading.Thread(target=self._read_sink, args=(sink,), daemon=True).start()
        for name in failing(self.config):
            self.spawn(name)

    def _read_sink(self, sink):
        for line in sink.stdout:
            self.last_rx = float(line)

    def respawn_missing(self):
        for name in failing(self.config):
            if name not in self.procs:
                self.spawn(name)

    def wait_healthy(self, stable=2.0, deadline=0.5, timeout=60.0):
        """Espera señal continua; devuelve False si no se recupera dentro del límite."""
        begin = time.monotonic()
        healthy_since = None
        while time.monotonic() - begin < timeout:
            now = time.monotonic()
            if now - self.last_rx < deadline:
                healthy_since = healthy_since or now
                if now - healthy_since >= stable:
                    return True
            else:
                healthy_since = None
            time.sleep(0.02)
        return False

    def stop(self):
        for name in list(self.procs):
            self.kill(name)


def run_trial(system, rng, lam, mttr, latency, deadline, max_seconds=1800.0):
    """Primer paso desde todo operativo; devuelve tiempos observado y lógico."""
    names = failing(system.config)
    t0 = time.monotonic()
    next_fail = {n: t0 + rng.exponential(1 / lam) for n in names}
    next_spawn, up_at = {}, {}
    kills = spawns = 0
    t_logical = None
    while True:
        time.sleep(0.005)
        now = time.monotonic()
        for name, due in list(next_fail.items()):
            if now >= due:
                system.kill(name)
                kills += 1
                del next_fail[name]
                next_spawn[name] = now + rng.exponential(mttr)
        for name, due in list(next_spawn.items()):
            if now >= due:
                system.spawn(name)
                spawns += 1
                del next_spawn[name]
                up_at[name] = now + latency
        for name, due in list(up_at.items()):
            if now >= due:
                del up_at[name]
                next_fail[name] = now + rng.exponential(1 / lam)
        up = {n: n in next_fail for n in names}
        if t_logical is None and not function_up(system.config, up):
            t_logical = now - t0
        last = system.last_rx
        if now - last > deadline:
            return {'t_obs': max(last - t0, 0.0), 't_logical': t_logical, 'kills': kills,
                    'spawns': spawns, 'censored': False}
        if now - t0 > max_seconds:
            return {'t_obs': now - t0, 't_logical': t_logical, 'kills': kills,
                    'spawns': spawns, 'censored': True}


def calibrate_latency(domain=90, n=30, seed=0):
    """Tiempo desde reinicio de un relé en serie hasta que vuelve la señal, con reparación inmediata."""
    system = System('d_series', domain)
    system.start()
    rng = np.random.default_rng(seed)
    values = []
    try:
        if not system.wait_healthy(timeout=30):
            raise RuntimeError('el sistema no arrancó')
        for _ in range(n):
            time.sleep(rng.uniform(1.0, 2.0))
            system.kill('l12')
            t_spawn = time.monotonic()
            system.spawn('l12')
            while system.last_rx < t_spawn + 0.05:
                if time.monotonic() - t_spawn > 30:
                    raise RuntimeError('sin recuperación tras 30 s')
                time.sleep(0.005)
            values.append(system.last_rx - t_spawn)
    finally:
        system.stop()
    return np.array(values)


if __name__ == '__main__':
    v = calibrate_latency()
    print(f'n={len(v)} media={v.mean():.3f}s sd={v.std(ddof=1):.3f}s p50={np.median(v):.3f}s max={v.max():.3f}s')
