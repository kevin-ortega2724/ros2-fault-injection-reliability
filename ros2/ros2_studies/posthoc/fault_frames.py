"""Fotogramas de la falla de fault_anatomy.py con una cámara virtual de Gazebo, en una copia del mundo; no abre ventanas."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import CONFIGS  # noqa: E402
from configs import SINK  # noqa: E402
from run_cell import CELL, stop_group  # noqa: E402
from supervisor import System  # noqa: E402

CASES = {'d_series': 'l12', 'd_parallel': 'la'}
RES = HERE / 'results'
CAMERA = """<model name="camara"><static>true</static><pose>5.6 -4.3 3.0 0 0.33 2.45</pose><link name="l"><sensor name="c" type="camera">
<always_on>true</always_on><update_rate>8</update_rate><camera><horizontal_fov>1.05</horizontal_fov><image><width>1600</width><height>1000</height></image>
<clip><near>0.1</near><far>60</far></clip><save enabled="true"><path>{path}</path></save></camera></sensor></link></model>
</world>"""


def capture(config, victim, domain, port):
    work = Path(tempfile.mkdtemp(dir=RES))
    world = work / 'cell.world'
    world.write_text((CELL / 'build' / 'cell.world').read_text().replace('</world>', CAMERA.format(path=work / 'img')))
    launch = (CELL / 'headless_cell.sh').read_text().replace('"$HERE/build/cell.world"', f'"{world}"')
    launch = launch.replace('HERE="$(cd "$(dirname "$0")" && pwd)"', f'HERE="{CELL}"')
    env = {**System(config, domain).env}
    cell = subprocess.Popen(['bash', '-c', launch, 'celda', str(domain), str(port)], cwd=CELL, env=env, stdout=subprocess.PIPE, text=True, start_new_session=True)
    if cell.stdout.readline().strip() != 'READY':
        raise RuntimeError('la celda no arrancó')
    log = work / 'ctrl.log'
    topics = ','.join(f'/mtbf/out_{i}' for i in CONFIGS[config][SINK].inputs)
    with open(log, 'w') as f:
        ctrl = subprocess.Popen([sys.executable, str(HERE / 'anatomy_controller.py'), '--heartbeat', topics], cwd=CELL, env=env, stdout=f, stderr=subprocess.DEVNULL, start_new_session=True)
    system = System(config, domain)
    system.start()
    try:
        if not system.wait_healthy(timeout=120):
            raise RuntimeError('sin señal')
        begin = time.time()
        while time.time() - begin < 120:
            size = log.stat().st_size
            time.sleep(.02)
            with open(log) as f:
                f.seek(size)
                if ' ev recoge' in f.read():
                    break
        else:
            raise RuntimeError('sin ciclo')
        time.sleep(1.2)
        system.kill(victim)
        wall, mono = time.time(), time.monotonic()
        time.sleep(4.0)
        system.spawn(victim)
        time.sleep(3.0)
    finally:
        system.stop()
        stop_group(ctrl)
        stop_group(cell)
    images = sorted((work / 'img').glob('*'), key=lambda p: p.stat().st_mtime)
    pick = {'before': max((p for p in images if p.stat().st_mtime < wall), key=lambda p: p.stat().st_mtime),
            'after': min(images, key=lambda p: abs(p.stat().st_mtime - wall - 2.5))}
    stamps = []
    for label, p in pick.items():
        shutil.copy(p, RES / f'frame_{config}_{label}.jpg' if p.suffix == '.jpg' else RES / f'frame_{config}_{label}{p.suffix}')
        stamps.append(f'{label} {p.stat().st_mtime - wall:+.3f}')
    events = [(float(l.split()[0]) - mono, l.split()[2]) for l in log.read_text().splitlines() if ' ev PARO' in l or ' ev MARCHA' in l]
    print(config, len(images), 'imágenes;', '; '.join(stamps), '; eventos', [(round(t, 3), e) for t, e in events if -1 < t < 7.5], flush=True)
    shutil.rmtree(work)


for i, (c, v) in enumerate(CASES.items()):
    capture(c, v, 85 + i, 11495 + i)
