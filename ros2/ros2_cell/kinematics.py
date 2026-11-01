"""Cinemática directa del UR5e a partir de su URDF."""
import math
import xml.etree.ElementTree as ET

import numpy as np

JOINTS = ['shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint', 'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint']


def rpy_mat(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def mat_rpy(R):
    return (math.atan2(R[2, 1], R[2, 2]), math.atan2(-R[2, 0], math.hypot(R[2, 1], R[2, 2])), math.atan2(R[1, 0], R[0, 0]))


def mat_quat(R):
    """Devuelve x, y, z, w."""
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return x, y, z, w


def tf(xyz, rpy):
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = rpy_mat(*rpy), xyz
    return T


def chain(root):
    joints = {j.find('child').get('link'): j for j in root.findall('joint')}
    out, link = [], 'tool0'
    while link in joints:
        j = joints[link]
        o = j.find('origin')
        xyz = [float(v) for v in o.get('xyz', '0 0 0').split()]
        rpy = [float(v) for v in o.get('rpy', '0 0 0').split()]
        out.insert(0, (tf(xyz, rpy), j.get('type') == 'revolute'))
        link = j.find('parent').get('link')
    return out


def load_chain(path):
    return chain(ET.parse(path).getroot())


def fk(links, q):
    T, i = np.eye(4), 0
    for origin, revolute in links:
        T = T @ origin
        if revolute:
            T = T @ tf((0, 0, 0), (0, 0, q[i]))
            i += 1
    return T
