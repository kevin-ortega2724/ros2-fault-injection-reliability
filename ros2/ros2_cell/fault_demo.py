"""Levanta una arquitectura del piloto e inyecta una falla cada cierto tiempo para ver el efecto en la celda."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ros2_pilot'))
from supervisor import System  # noqa: E402


def main(config='d_triangle', victim='p3', every=12.0, down=6.0, cycles=3):
    system = System(config, 30)
    system.start()
    if not system.wait_healthy(timeout=60):
        raise RuntimeError('sin señal')
    t0 = time.monotonic()
    print('0.000 arquitectura lista', flush=True)
    try:
        for _ in range(cycles):
            time.sleep(every)
            system.kill(victim)
            print(f'{time.monotonic() - t0:.3f} falla {victim}', flush=True)
            time.sleep(down)
            system.spawn(victim)
            print(f'{time.monotonic() - t0:.3f} reinicio {victim}', flush=True)
        time.sleep(every)
    finally:
        system.stop()


if __name__ == '__main__':
    main()
