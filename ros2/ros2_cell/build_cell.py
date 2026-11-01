"""Modela la celda en CadQuery y genera mallas STL, mundo SDF y brazo UR5e en pose fija."""
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from scipy.optimize import minimize

from kinematics import JOINTS, chain, fk, mat_rpy, tf

HERE = Path(__file__).resolve().parent
MODEL = HERE / 'models' / 'cell_meshes'
BUILD = HERE / 'build'
TOL, ANG = 0.0015, 0.2

BELT_TOP, BELT_L, BELT_W, CONV_X = 0.85, 3.2, 0.46, 0.72
PALLET_X, PALLET_Y = 1.25, 2.8
GRIP_LEN, OUT_TOP, OUT_POS, PICK_Y, BOX_H = 0.125, 0.72, (0.05, 0.62), -0.05, 0.18
PEDESTAL_H = 0.75

# ambiente/difuso R G B, especular, emisión opcional, alfa opcional
MATERIALS = {
    'alu': ((0.72, 0.74, 0.76), 0.7), 'steel': ((0.55, 0.57, 0.6), 0.9), 'dark': ((0.09, 0.09, 0.1), 0.25),
    'rubber': ((0.045, 0.045, 0.05), 0.12), 'blue': ((0.06, 0.2, 0.42), 0.45), 'yellow': ((0.95, 0.72, 0.05), 0.35),
    'black': ((0.02, 0.02, 0.02), 0.3), 'cabinet': ((0.78, 0.78, 0.75), 0.25), 'plastic': ((0.13, 0.14, 0.16), 0.3),
    'card': ((0.66, 0.47, 0.27), 0.05), 'tape': ((0.82, 0.7, 0.5), 0.3), 'label': ((0.95, 0.95, 0.92), 0.05),
    'wood': ((0.62, 0.45, 0.27), 0.04), 'red': ((0.8, 0.04, 0.03), 0.5), 'green': ((0.1, 0.65, 0.2), 0.5),
    'floor': ((0.5, 0.52, 0.53), 0.15), 'wall': ((0.74, 0.76, 0.77), 0.05), 'motor': ((0.12, 0.26, 0.3), 0.45),
    'screen': ((0.04, 0.2, 0.32), 0.8, (0.05, 0.28, 0.42)), 'lamp_g': ((0.1, 0.8, 0.25), 0.6, (0.1, 0.9, 0.3)), 'lamp_g_off': ((0.05, 0.25, 0.1), 0.6), 'lamp_r_on': ((1.0, 0.1, 0.08), 0.6, (1.0, 0.08, 0.05)),
    'lamp_a': ((0.6, 0.4, 0.05), 0.6), 'lamp_r': ((0.45, 0.05, 0.05), 0.6),
    'beam': ((0.95, 0.05, 0.05), 0.0, (0.9, 0.05, 0.05), 0.45),
}


def box(s, c=(0, 0, 0), f=0.0, edges='|Z'):
    w = cq.Workplane().box(*s)
    if f:
        w = w.edges(edges).fillet(f)
    return w.val().moved(cq.Location(cq.Vector(*c)))


def cyl(r, h, c=(0, 0, 0), axis='z'):
    d = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[axis]
    p = cq.Vector(*c) - cq.Vector(*d) * (h / 2)
    return cq.Solid.makeCylinder(r, h, p, cq.Vector(*d))


def tslot(a, length, c=(0, 0, 0), axis='z'):
    """Perfil de aluminio con ranuras en T y agujero central."""
    w = cq.Workplane().rect(a, a).extrude(length).edges('|Z').fillet(a * 0.06)
    slot, depth = a * 0.26, a * 0.3
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        size = (depth, slot) if sx else (slot, depth)
        w = w.cut(cq.Workplane().center(sx * (a - depth) / 2, sy * (a - depth) / 2).rect(*size).extrude(length))
    w = w.cut(cq.Workplane().circle(a * 0.14).extrude(length))
    s = w.val().moved(cq.Location(cq.Vector(0, 0, -length / 2)))
    if axis == 'x':
        s = s.rotate(cq.Vector(), cq.Vector(0, 1, 0), 90)
    elif axis == 'y':
        s = s.rotate(cq.Vector(), cq.Vector(1, 0, 0), 90)
    return s.moved(cq.Location(cq.Vector(*c)))


class Assembly:
    def __init__(self, name):
        self.name, self.parts = name, {}

    def add(self, mat, *shapes):
        self.parts.setdefault(mat, []).extend(shapes)

    def export(self):
        for mat, shapes in self.parts.items():
            cq.Compound.makeCompound(shapes).exportStl(str(MODEL / f'{self.name}_{mat}.stl'), TOL, ANG)


def conveyor():
    """Origen en el piso, bajo el centro de la banda; transporte a lo largo de Y."""
    a = Assembly('conveyor')
    d = 0.11
    zc = BELT_TOP - d / 2
    belt = (cq.Workplane('YZ').center(0, zc).slot2D(BELT_L, d).slot2D(BELT_L - 0.012, d - 0.012)
            .extrude(BELT_W / 2, both=True))
    a.add('rubber', belt.val())
    half = BELT_L / 2 - d / 2
    for y in (-half, half):
        a.add('steel', cyl(0.047, BELT_W, (0, y, zc), 'x'), cyl(0.012, BELT_W + 0.2, (0, y, zc), 'x'))
    for y in np.arange(-half + 0.28, half - 0.1, 0.28):
        a.add('steel', cyl(0.024, BELT_W - 0.01, (0, y, BELT_TOP - 0.135), 'x'))
    a.add('alu', box((BELT_W - 0.02, BELT_L - 0.14, 0.006), (0, 0, BELT_TOP - 0.012)))
    for sx in (-1, 1):
        x = sx * (BELT_W / 2 + 0.025)
        side = (cq.Workplane().box(0.05, BELT_L + 0.03, 0.17)
                .cut(cq.Workplane().center(-sx * 0.006, 0).rect(0.05, BELT_L + 0.1).extrude(0.065, both=True)))
        a.add('alu', side.val().moved(cq.Location(cq.Vector(x, 0, zc - 0.03))))
        for y in np.arange(-BELT_L / 2 + 0.12, BELT_L / 2, 0.24):
            a.add('steel', cyl(0.006, 0.006, (x + sx * 0.026, y, zc + 0.04), 'x'),
                  cyl(0.006, 0.006, (x + sx * 0.026, y, zc - 0.1), 'x'))
        for y in (-half, half):
            a.add('plastic', box((0.03, 0.09, 0.09), (x + sx * 0.03, y, zc), 0.008, '|X'))
            a.add('steel', cyl(0.018, 0.012, (x + sx * 0.05, y, zc), 'x'))
    # patas, travesaños y niveladores
    leg_h = zc - 0.115 - 0.05
    for y in (-1.3, 0.0, 1.3):
        for sx in (-1, 1):
            x = sx * (BELT_W / 2 + 0.025)
            a.add('alu', tslot(0.06, leg_h, (x, y, 0.05 + leg_h / 2)))
            a.add('plastic', cyl(0.036, 0.012, (x, y, 0.006)))
            a.add('steel', cyl(0.009, 0.05, (x, y, 0.03)))
            a.add('steel', box((0.08, 0.08, 0.006), (x, y, 0.056), 0.012))
        for z in (0.2, leg_h - 0.02):
            a.add('alu', tslot(0.04, BELT_W + 0.0, (0, y, z), 'x'))
    for sx in (-1, 1):
        a.add('alu', tslot(0.04, 2.6, (sx * (BELT_W / 2 + 0.025), 0, 0.2), 'y'))
    # guías laterales de acero sobre soportes
    for sx in (-1, 1):
        x = sx * (BELT_W / 2 - 0.005)
        a.add('steel', cyl(0.01, BELT_L - 0.1, (x, 0, BELT_TOP + 0.095), 'y'))
        for y in np.arange(-1.35, 1.4, 0.54):
            a.add('steel', cyl(0.007, 0.13, (x + sx * 0.03, y, BELT_TOP + 0.03)),
                  cyl(0.006, 0.05, (x + sx * 0.015, y, BELT_TOP + 0.095), 'x'))
            a.add('dark', box((0.036, 0.05, 0.03), (x + sx * 0.032, y, BELT_TOP - 0.03), 0.004))
    # motorreductor de eje hueco en el tambor; el motor corre paralelo al bastidor
    mx, my, mz = BELT_W / 2 + 0.14, half, zc
    a.add('motor', box((0.12, 0.13, 0.15), (mx, my, mz), 0.015, '|X'),
          cyl(0.056, 0.2, (mx, my - 0.165, mz), 'y'), cyl(0.066, 0.016, (mx, my - 0.073, mz), 'y'))
    for i in range(7):
        a.add('motor', cyl(0.062, 0.006, (mx, my - 0.095 - i * 0.021, mz), 'y'))
    a.add('dark', cyl(0.06, 0.05, (mx, my - 0.29, mz), 'y'))
    a.add('dark', box((0.07, 0.08, 0.04), (mx, my - 0.16, mz + 0.074), 0.006))
    a.add('steel', box((0.018, 0.05, 0.14), (mx - 0.085, my, mz - 0.03)))
    return a


def carton(name='carton', s=(0.3, 0.22, 0.18)):
    """Origen en la base de la caja."""
    a = Assembly(name)
    a.add('card', box(s, (0, 0, s[2] / 2), 0.005))
    a.add('tape', box((s[0] + 0.002, 0.05, 0.001), (0, 0, s[2] + 0.0005)),
          box((0.001, 0.05, s[2] * 0.35), (s[0] / 2 + 0.0005, 0, s[2] * 0.825)),
          box((0.001, 0.05, s[2] * 0.35), (-s[0] / 2 - 0.0005, 0, s[2] * 0.825)))
    a.add('label', box((0.09, 0.001, 0.06), (0.06, -s[1] / 2 - 0.0005, s[2] * 0.45)))
    a.add('black', box((0.06, 0.0012, 0.018), (0.06, -s[1] / 2 - 0.0007, s[2] * 0.45)))
    return a


def pedestal():
    a = Assembly('pedestal')
    a.add('blue', box((0.5, 0.5, 0.02), (0, 0, 0.01), 0.03), box((0.24, 0.24, 0.7), (0, 0, 0.37), 0.02))
    a.add('steel', cyl(0.1, 0.03, (0, 0, PEDESTAL_H - 0.015)))
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        a.add('steel', cyl(0.016, 0.015, (sx * 0.2, sy * 0.2, 0.027)), cyl(0.009, 0.03, (sx * 0.2, sy * 0.2, 0.04)))
        a.add('dark', cyl(0.007, 0.006, (sx * 0.07, sy * 0.07, PEDESTAL_H)))
    for ang in (0, 90, 180, 270):
        g = (cq.Workplane('XZ').polyline([(0.12, 0.02), (0.235, 0.02), (0.12, 0.26)]).close()
             .extrude(0.006, both=True))
        a.add('blue', g.val().rotate(cq.Vector(), cq.Vector(0, 0, 1), ang))
    a.add('dark', box((0.002, 0.14, 0.2), (0.121, 0, 0.45), 0.004, '|X'))
    a.add('yellow', box((0.002, 0.1, 0.03), (0.1215, 0, 0.6)))
    return a


def cabinet():
    """Puerta hacia -Y."""
    a = Assembly('cabinet')
    w, dp, h, plinth = 0.8, 0.4, 1.8, 0.1
    zc = plinth + h / 2
    a.add('dark', box((w, dp, plinth), (0, 0, plinth / 2)))
    a.add('cabinet', box((w, dp, h), (0, 0, zc), 0.012), box((w - 0.03, 0.022, h - 0.03), (0, -dp / 2 - 0.011, zc), 0.012, '|Y'))
    for z in (plinth + 0.3, plinth + h - 0.3):
        a.add('dark', box((0.02, 0.02, 0.09), (w / 2 - 0.012, -dp / 2 - 0.02, z), 0.004))
    a.add('dark', box((0.025, 0.03, 0.17), (-w / 2 + 0.05, -dp / 2 - 0.035, zc - 0.05), 0.008))
    # rejillas de ventilación
    for i in range(7):
        a.add('dark', box((0.22, 0.004, 0.012), (0.16, -dp / 2 - 0.023, plinth + 0.09 + i * 0.024)))
    # HMI
    z_hmi = plinth + 1.28
    a.add('plastic', box((0.3, 0.018, 0.22), (0.02, -dp / 2 - 0.03, z_hmi), 0.01, '|Y'))
    a.add('screen', box((0.26, 0.002, 0.17), (0.02, -dp / 2 - 0.04, z_hmi)))
    # mandos
    z_btn = plinth + 1.0
    a.add('yellow', box((0.1, 0.004, 0.1), (0.2, -dp / 2 - 0.024, z_btn), 0.012, '|Y'))
    a.add('red', cyl(0.033, 0.03, (0.2, -dp / 2 - 0.04, z_btn), 'y'))
    a.add('green', cyl(0.016, 0.014, (0.0, -dp / 2 - 0.028, z_btn), 'y'))
    a.add('label', cyl(0.016, 0.014, (-0.07, -dp / 2 - 0.028, z_btn), 'y'))
    a.add('steel', box((0.05, 0.015, 0.05), (-0.17, -dp / 2 - 0.028, z_btn), 0.006, '|Y'))
    a.add('yellow', box((0.09, 0.002, 0.08), (0.2, -dp / 2 - 0.023, plinth + 0.5)))
    # baliza
    top = plinth + h
    a.add('dark', cyl(0.03, 0.04, (0.28, 0.05, top + 0.02)))
    for mat, i in (('lamp_g_off', 0), ('lamp_a', 1), ('lamp_r', 2)):
        a.add(mat, cyl(0.03, 0.065, (0.28, 0.05, top + 0.075 + i * 0.07)))
    a.add('dark', cyl(0.03, 0.012, (0.28, 0.05, top + 0.25)))
    return a


def fence_panel(length=1.6, height=2.0):
    """Panel en el plano YZ con poste en cada extremo; origen al centro de la base."""
    a = Assembly(f'fence_{int(length * 100)}')
    for y in (-length / 2,):
        a.add('yellow', box((0.06, 0.06, height), (0, y, height / 2), 0.005))
        a.add('yellow', box((0.14, 0.14, 0.008), (0, y, 0.004)))
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            a.add('steel', cyl(0.008, 0.012, (sx * 0.05, y + sy * 0.05, 0.012)))
    z0, z1, lp = 0.15, height - 0.04, length - 0.08
    for z in (z0, z1, (z0 + z1) / 2):
        a.add('yellow', box((0.022, lp, 0.022), (0, 0, z)))
    for y in (-lp / 2, lp / 2):
        a.add('yellow', box((0.022, 0.022, z1 - z0), (0, y, (z0 + z1) / 2)))
    for y in np.arange(-lp / 2 + 0.05, lp / 2, 0.05):
        a.add('black', box((0.003, 0.003, z1 - z0), (0, y, (z0 + z1) / 2)))
    for z in np.arange(z0 + 0.05, z1, 0.05):
        a.add('black', box((0.003, lp, 0.003), (0, 0, z)))
    return a


def fence_post(height=2.0):
    a = Assembly('fence_post')
    a.add('yellow', box((0.06, 0.06, height), (0, 0, height / 2), 0.005), box((0.14, 0.14, 0.008), (0, 0, 0.004)))
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        a.add('steel', cyl(0.008, 0.012, (sx * 0.05, sy * 0.05, 0.012)))
    return a


def lamp_on(mat):
    """Capa encendida de la baliza, algo mayor que el segmento apagado."""
    a = Assembly(f'on_{mat}')
    a.add(mat, cyl(0.0315, 0.066))
    return a


def sensors():
    """Barrera fotoeléctrica transversal; origen en el centro de la banda, a nivel de piso."""
    a = Assembly('sensor')
    z, off = BELT_TOP + 0.075, BELT_W / 2 + 0.075
    for sx in (-1, 1):
        a.add('steel', box((0.05, 0.03, 0.004), (sx * (off - 0.01), 0, BELT_TOP - 0.05)),
              box((0.004, 0.03, 0.16), (sx * (off + 0.02), 0, BELT_TOP + 0.02)))
    a.add('plastic', box((0.03, 0.05, 0.07), (off, 0, z), 0.006, '|X'))
    a.add('dark', cyl(0.012, 0.004, (off - 0.017, 0, z), 'x'))
    a.add('lamp_g', box((0.002, 0.008, 0.006), (off + 0.016, 0.012, z + 0.022)))
    a.add('red', cyl(0.004, 0.02, (off, 0, z - 0.044)))
    a.add('steel', box((0.012, 0.05, 0.07), (-off, 0, z), 0.004, '|X'))
    a.add('red', box((0.003, 0.04, 0.05), (-off + 0.0075, 0, z)))
    a.add('beam', cyl(0.0025, 2 * off - 0.03, (0, 0, z), 'x'))
    return a


def pallet():
    a = Assembly('pallet')
    for x in np.linspace(-0.55, 0.55, 7):
        a.add('wood', box((0.1, 0.8, 0.022), (x, 0, 0.133)))
    for x in (-0.55, 0.0, 0.55):
        a.add('wood', box((0.1, 0.8, 0.022), (x, 0, 0.011)))
        for y in (-0.33, 0.0, 0.33):
            a.add('wood', box((0.1, 0.13, 0.078), (x, y, 0.061)))
        a.add('wood', box((0.1, 0.8, 0.022), (x, 0, 0.111)))
    return a


def gripper():
    """Efector de vacío con cuatro ventosas; +Z sale de la brida, origen en tool0, punta a GRIP_LEN."""
    a = Assembly('gripper')
    a.add('steel', cyl(0.038, 0.012, (0, 0, 0.006)))
    a.add('dark', cyl(0.03, 0.03, (0, 0, 0.027)))
    a.add('blue', box((0.07, 0.07, 0.03), (0, 0, 0.055), 0.006))
    a.add('alu', tslot(0.02, 0.24, (0, 0, 0.078), 'x'), tslot(0.02, 0.16, (0, 0, 0.078), 'y'))
    for x, y in ((0.1, 0), (-0.1, 0), (0, 0.065), (0, -0.065)):
        a.add('steel', cyl(0.005, 0.02, (x, y, 0.095)))
        a.add('rubber', cyl(0.016, 0.012, (x, y, GRIP_LEN - 0.006)), cyl(0.009, 0.012, (x, y, GRIP_LEN - 0.016)))
    a.add('dark', cyl(0.004, 0.2, (0.0, 0.016, 0.05), 'x'))
    return a


def outfeed():
    """Mesa de rodillos de salida; origen en el piso."""
    a = Assembly('outfeed')
    w, l, h = 0.46, 0.5, OUT_TOP
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.add('alu', tslot(0.05, h - 0.03, (sx * (w / 2 - 0.03), sy * (l / 2 - 0.03), (h - 0.03) / 2)))
            a.add('plastic', cyl(0.03, 0.01, (sx * (w / 2 - 0.03), sy * (l / 2 - 0.03), 0.005)))
        a.add('alu', tslot(0.04, l, (sx * (w / 2 - 0.03), 0, h - 0.05), 'y'))
        a.add('alu', tslot(0.04, l - 0.1, (sx * (w / 2 - 0.03), 0, 0.2), 'y'))
    for y in np.arange(-l / 2 + 0.04, l / 2, 0.06):
        a.add('steel', cyl(0.02, w - 0.04, (0, y, h - 0.02), 'x'))
    return a


def site():
    """Marcas de piso y ductos."""
    a = Assembly('site')
    def rect(x0, x1, y0, y1, t=0.08, mat='yellow'):
        a.add(mat, box((x1 - x0 + t, t, 0.003), ((x0 + x1) / 2, y0, 0.0015)),
              box((x1 - x0 + t, t, 0.003), ((x0 + x1) / 2, y1, 0.0015)),
              box((t, y1 - y0, 0.003), (x0, (y0 + y1) / 2, 0.0015)),
              box((t, y1 - y0, 0.003), (x1, (y0 + y1) / 2, 0.0015)))
    rect(-1.3, 1.6, -2.2, 2.2)
    # franja de advertencia frente a la celda
    for i in range(22):
        y = -2.2 + i * 0.2
        stripe = cq.Workplane().polyline([(1.68, y), (1.86, y + 0.1), (1.86, y + 0.3), (1.68, y + 0.2)]).close().extrude(0.004)
        a.add('yellow' if i % 2 else 'black', stripe.val())
    # ducto de cables con rampa, del gabinete a la banda
    a.add('dark', box((0.1, 1.31, 0.025), (CONV_X + 0.255, -1.995, 0.0125), 0.007, '|Y'))
    return a


# --------- brazo articulado ---------------------------------------------------------
def build_arm(targets):
    """Genera el URDF con ros2_control y resuelve las poses articulares de cada objetivo."""
    prefix = subprocess.check_output(['ros2', 'pkg', 'prefix', 'ur_description'], text=True).strip()
    xml = subprocess.check_output(['xacro', f'{prefix}/share/ur_description/urdf/ur.urdf.xacro',
                                   'ur_type:=ur5e', 'name:=ur5e'], text=True)
    root = ET.fromstring(xml)
    links = chain(root)
    poses, q = {}, np.array([3.26, -2.1, -0.95, -1.64, 1.57, 0.0])
    for name, target in targets.items():
        goal = np.array(target) - [0, 0, PEDESTAL_H]

        def cost(q):
            T = fk(links, q)
            return np.sum((T[:3, 3] - goal) ** 2) + 0.3 * (T[2, 2] + 1) ** 2

        r = minimize(cost, q, method='BFGS')
        if r.fun > 1e-5:
            raise RuntimeError(f'IK sin solución para {name}: {r.fun}')
        q = r.x
        poses[name] = q.tolist()
    for e in root.findall('ros2_control'):
        root.remove(e)
    control = ET.SubElement(root, 'ros2_control', name='GazeboSystem', type='system')
    ET.SubElement(ET.SubElement(control, 'hardware'), 'plugin').text = 'gazebo_ros2_control/GazeboSystem'
    home = poses['hover_pick']
    for name, value in zip(JOINTS, home):
        joint = ET.SubElement(control, 'joint', name=name)
        ET.SubElement(joint, 'command_interface', name='position')
        state = ET.SubElement(joint, 'state_interface', name='position')
        ET.SubElement(state, 'param', name='initial_value').text = str(value)
        ET.SubElement(joint, 'state_interface', name='velocity')
    plugin = ET.SubElement(ET.SubElement(root, 'gazebo'), 'plugin', name='gazebo_ros2_control', filename='libgazebo_ros2_control.so')
    ET.SubElement(plugin, 'parameters').text = str(HERE / 'controllers.yaml')
    for link in root.findall('link'):
        ET.SubElement(ET.SubElement(root, 'gazebo', reference=link.get('name')), 'gravity').text = '0'
    (BUILD / 'ur5e_control.urdf').write_text(ET.tostring(root, encoding='unicode'))
    (BUILD / 'arm_poses.json').write_text(json.dumps(poses, indent=1))
    T = fk(links, home)
    T[2, 3] += PEDESTAL_H
    return T


# --------- mundo SDF --------------------------------------------------------------------
def visual(asm, mat, idx):
    m = MATERIALS[mat]
    col, spec = m[0], m[1]
    alpha = m[3] if len(m) > 3 else 1
    emis = m[2] if len(m) > 2 else (0, 0, 0)
    rgba = ' '.join(map(str, (*col, alpha)))
    return f'''<visual name="v{idx}"><geometry><mesh><uri>model://cell_meshes/{asm}_{mat}.stl</uri></mesh></geometry>
<transparency>{1 - alpha}</transparency>
<material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse><specular>{spec} {spec} {spec} 1</specular><emissive>{' '.join(map(str, emis))} 1</emissive></material></visual>'''


PLACED = []


def model(name, asm, pose):
    PLACED.append((name, asm, pose))
    body = '\n'.join(visual(asm.name, mat, i) for i, mat in enumerate(asm.parts))
    return f'<model name="{name}"><static>true</static><pose>{" ".join(f"{v:.5f}" for v in pose)}</pose><link name="l">{body}</link></model>'


def moving_box(name, asm, pose, size):
    """Caja cinemática: la mueve line_controller y la detecta la barrera por su colisión."""
    PLACED.append((name, asm, pose))
    body = '\n'.join(visual(asm.name, mat, i) for i, mat in enumerate(asm.parts))
    s = ' '.join(map(str, size))
    return f'''<model name="{name}"><pose>{" ".join(f"{v:.5f}" for v in pose)}</pose><link name="l"><kinematic>true</kinematic><gravity>false</gravity>
<collision name="c"><pose>0 0 {size[2] / 2} 0 0 0</pose><geometry><box><size>{s}</size></box></geometry></collision>{body}</link></model>'''


def barrier(x, y, z):
    return f'''<model name="barrera"><static>true</static><pose>{x} {y} {z} 0 0 {math.pi}</pose><link name="l"><sensor name="ray" type="ray"><always_on>true</always_on><update_rate>40</update_rate>
<ray><scan><horizontal><samples>1</samples><resolution>1</resolution><min_angle>0</min_angle><max_angle>0</max_angle></horizontal></scan><range><min>0.01</min><max>0.7</max><resolution>0.001</resolution></range></ray>
<plugin name="barrera" filename="libgazebo_ros_ray_sensor.so"><ros><remapping>~/out:=/cell/barrier</remapping></ros><output_type>sensor_msgs/LaserScan</output_type><frame_name>barrera</frame_name></plugin></sensor></link></model>'''


def check_overlaps(allowed):
    """Informa cruces de cajas envolventes entre modelos colocados."""
    bounds = {}
    for name, asm, pose in PLACED:
        T = tf(pose[:3], pose[3:])
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for mat in asm.parts:
            m = trimesh.load_mesh(MODEL / f'{asm.name}_{mat}.stl')
            v = (T[:3, :3] @ m.vertices.T).T + T[:3, 3]
            lo, hi = np.minimum(lo, v.min(0)), np.maximum(hi, v.max(0))
        bounds[name] = lo, hi
    names, bad = list(bounds), []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d = np.minimum(bounds[a][1], bounds[b][1]) - np.maximum(bounds[a][0], bounds[b][0])
            if (d > 0.002).all() and not any((a.startswith(p) and b.startswith(q)) or (a.startswith(q) and b.startswith(p)) for p, q in allowed):
                bad.append((a, b, np.round(d, 3).tolist()))
    print('cruces:', bad if bad else 'ninguno')
    return bad


def plane_box(name, size, c, mat):
    col = MATERIALS[mat][0]
    rgba = ' '.join(map(str, (*col, 1)))
    s = ' '.join(map(str, size))
    return f'''<model name="{name}"><static>true</static><pose>{c[0]} {c[1]} {c[2]} 0 0 0</pose><link name="l">
<collision name="c"><geometry><box><size>{s}</size></box></geometry></collision>
<visual name="v"><geometry><box><size>{s}</size></box></geometry><material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse><specular>0.1 0.1 0.1 1</specular></material></visual></link></model>'''


def main():
    MODEL.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(exist_ok=True)
    (MODEL / 'model.config').write_text('<?xml version="1.0"?><model><name>cell_meshes</name><version>1.0</version><sdf version="1.6">model.sdf</sdf></model>')
    (MODEL / 'model.sdf').write_text('<?xml version="1.0"?><sdf version="1.6"><model name="cell_meshes"><static>true</static><link name="l"/></model></sdf>')
    conv, box_a, ped, cab, fence16, fence12, sens, pal, grip, ste = (
        conveyor(), carton(), pedestal(), cabinet(), fence_panel(1.6), fence_panel(1.2),
        sensors(), pallet(), gripper(), site())
    post, on_g, on_r, out = fence_post(), lamp_on('lamp_g'), lamp_on('lamp_r_on'), outfeed()
    for a in (out, conv, box_a, ped, cab, fence16, fence12, sens, pal, grip, ste, post, on_g, on_r):
        a.export()

    pick_z, place_z = BELT_TOP + BOX_H + GRIP_LEN, OUT_TOP + BOX_H + GRIP_LEN
    T_tool = build_arm({'hover_pick': (CONV_X, PICK_Y, pick_z + 0.2), 'pick': (CONV_X, PICK_Y, pick_z),
                        'hover_place': (*OUT_POS, place_z + 0.2), 'place': (*OUT_POS, place_z)})
    items = [
        model('banda', conv, (CONV_X, 0, 0, 0, 0, 0)), model('pedestal', ped, (0, 0, 0, 0, 0, 0)),
        model('gabinete', cab, (0.9, -2.85, 0, 0, 0, 0)), model('sensor', sens, (CONV_X, -0.55, 0, 0, 0, 0)),
        model('pinza', grip, (*T_tool[:3, 3], *mat_rpy(T_tool[:3, :3]))), model('marcas', ste, (0, 0, 0, 0, 0, 0)),
        model('pallet', pal, (PALLET_X, PALLET_Y, 0, 0, 0, 0)),
    ]
    for i, pose in enumerate(((*OUT_POS, OUT_TOP), (CONV_X, -1.45, BELT_TOP), (CONV_X, -0.85, BELT_TOP))):
        items.append(moving_box(f'caja{i}', box_a, (*pose, 0, 0, math.pi / 2), (0.3, 0.22, 0.18)))
    n = 0
    for lz, cells in enumerate((range(9), range(9), (0, 1, 3, 4))):
        for c in cells:
            items.append(model(f'carga{n}', box_a, (PALLET_X + (c % 3 - 1) * 0.32, PALLET_Y + (c // 3 - 1) * 0.24, 0.144 + lz * 0.18, 0, 0, 0)))
            n += 1
    # cerramiento posterior y laterales; el frente queda abierto para ver la celda
    for i, y in enumerate((-1.6, 0.0, 1.6)):
        items.append(model(f'valla_p{i}', fence16, (-1.15, y, 0, 0, 0, 0)))
    for i, x in enumerate((-0.35,)):
        items.append(model(f'valla_a{i}', fence16, (x, -2.4, 0, 0, 0, math.pi / 2)))
        items.append(model(f'valla_b{i}', fence16, (x, 2.4, 0, 0, 0, math.pi / 2)))
    items.append(model('mesa_salida', out, (*OUT_POS, 0, 0, 0, 0)))
    items.append(model('poste_fin', post, (-1.15, 2.4, 0, 0, 0, 0)))
    # capas encendidas de la baliza: line_controller las sube o las baja bajo el piso
    items.append(model('lampara_verde', on_g, (0.9 + 0.28, -2.85 + 0.05, 1.975, 0, 0, 0)))
    items.append(model('lampara_roja', on_r, (0.9 + 0.28, -2.85 + 0.05, -1.0, 0, 0, 0)))
    items.append(barrier(CONV_X + 0.27, -0.55, BELT_TOP + 0.075))
    check_overlaps((('banda', 'sensor'), ('banda', 'caja'), ('banda', 'pinza'), ('banda', 'marcas'), ('pedestal', 'marcas'),
                    ('valla', 'valla'), ('valla', 'poste'), ('valla', 'marcas'), ('poste', 'marcas'), ('carga', 'pallet'),
                    ('carga', 'carga'), ('gabinete', 'lampara'), ('sensor', 'caja'), ('pinza', 'caja'), ('mesa', 'pedestal'), ('marcas', 'mesa'), ('marcas', 'marcas')))
    items.append(plane_box('piso', (24, 24, 0.02), (0, 0, -0.01), 'floor'))
    items.append(plane_box('muro_x', (0.2, 16, 5), (-4, 0, 2.5), 'wall'))
    items.append(plane_box('muro_y', (16, 0.2, 5), (0, 5.5, 2.5), 'wall'))
    world = f'''<?xml version="1.0"?><sdf version="1.6"><world name="celda">
<scene><ambient>0.42 0.42 0.44 1</ambient><background>0.8 0.83 0.86 1</background><shadows>true</shadows><grid>false</grid><origin_visual>false</origin_visual></scene>
<light name="sol" type="directional"><cast_shadows>true</cast_shadows><pose>0 0 12 0 0 0</pose><diffuse>0.8 0.8 0.78 1</diffuse><specular>0.25 0.25 0.25 1</specular><direction>-0.45 0.35 -0.82</direction></light>
<light name="relleno1" type="point"><pose>3 -3 4 0 0 0</pose><diffuse>0.35 0.35 0.35 1</diffuse><specular>0.1 0.1 0.1 1</specular><attenuation><range>20</range><constant>0.9</constant><linear>0.02</linear><quadratic>0.002</quadratic></attenuation></light>
<gui><camera name="user_camera"><pose>5.6 -4.3 3.0 0 0.33 2.45</pose></camera></gui>
<plugin name="gazebo_ros_state" filename="libgazebo_ros_state.so"><ros><namespace>/gazebo</namespace></ros><update_rate>1.0</update_rate></plugin>
{chr(10).join(items)}
</world></sdf>'''
    (BUILD / 'cell.world').write_text(world)
    print('mallas', len(list(MODEL.glob('*.stl'))), 'MB', round(sum(p.stat().st_size for p in MODEL.glob('*.stl')) / 1e6, 1))


if __name__ == '__main__':
    main()
