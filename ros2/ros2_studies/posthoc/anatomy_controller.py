"""Controlador congelado de la celda, sin cambios de lógica; solo registra latidos, articulaciones y eventos con el reloj del sistema."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ros2_cell'))
import line_controller as lc  # noqa: E402


class Recorded(lc.Cell):
    def log(self, text):
        print(f'{time.monotonic():.4f} ev {text}', flush=True)

    def on_beat(self, msg):
        print(f'{time.monotonic():.4f} beat', flush=True)
        super().on_beat(msg)

    def on_joints(self, msg):
        super().on_joints(msg)
        if self.q is not None:
            print(f'{time.monotonic():.4f} q ' + ' '.join(f'{v:.5f}' for v in self.q), flush=True)


lc.Cell = Recorded
lc.main()
