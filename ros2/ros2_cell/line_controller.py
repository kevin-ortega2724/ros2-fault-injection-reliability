"""Controla la celda: banda, barrera, ciclo de recogida y baliza; todo se detiene si falta la señal de la arquitectura."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from gazebo_msgs.msg import EntityState
from gazebo_msgs.srv import SetEntityState
from geometry_msgs.msg import Point, Pose, Quaternion
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import UInt64
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from kinematics import JOINTS, load_chain, fk, mat_quat

BUILD = Path(__file__).resolve().parent / 'build'
CONV_X, BELT_TOP, SPEED, Y_IN = 0.72, 0.85, 0.25, -1.45
BARRIER_Y, PICK_Y, Y_END, BOX_LEN, BOX_H, MIN_GAP = -0.55, -0.05, 1.45, 0.3, 0.18, 0.6
OUT_POS, OUT_TOP, GRIP_LEN, PEDESTAL_H = (0.05, 0.62), 0.72, 0.125, 0.75
LAMP = {True: ('lampara_verde', 'lampara_roja'), False: ('lampara_roja', 'lampara_verde')}
LAMP_Z = {'lampara_verde': 1.975, 'lampara_roja': 2.115}
LAMP_XY = (1.18, -2.8)
YAW_90 = Quaternion(z=0.70710678, w=0.70710678)
# paso del ciclo: (pose articular, duración en s, acción al llegar)
CYCLE = [('pick', 1.2, 'grasp'), ('hover_pick', 1.2, None), ('hover_place', 3.0, None), ('place', 1.2, 'release'),
         ('hover_place', 1.2, None), ('hover_pick', 3.0, 'done')]


class Cell(Node):
    def __init__(self, heartbeat, deadline):
        super().__init__('line_controller')
        self.deadline, self.last_rx = deadline, 0.0
        self.boxes = {'caja1': -1.45, 'caja2': -0.85}
        self.running, self.blocked, self.seen, self.produced = None, False, 0, 0
        self.tracked, self.at_pick, self.carried, self.parked, self.waiting = [], None, None, None, ['caja0']
        self.step, self.commanded = None, None
        self.q = None
        self.poses = json.loads((BUILD / 'arm_poses.json').read_text())
        self.links = load_chain(BUILD / 'ur5e_control.urdf')
        self.t0 = self.tick_at = time.monotonic()
        self.set_state = self.create_client(SetEntityState, '/gazebo/set_entity_state')
        self.traj = self.create_publisher(JointTrajectory, '/joint_trajectory_controller/joint_trajectory', 10)
        self.out = self.create_publisher(UInt64, '/cell/produced', 10)
        for topic in heartbeat.split(','):
            self.create_subscription(UInt64, topic, self.on_beat, QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(LaserScan, '/cell/barrier', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(JointState, '/joint_states', self.on_joints, 10)
        self.create_timer(1 / 30, self.tick)

    def log(self, text):
        print(f'{time.monotonic() - self.t0:.3f} {text}', flush=True)

    def on_beat(self, _):
        self.last_rx = time.monotonic()

    def on_joints(self, msg):
        order = {n: p for n, p in zip(msg.name, msg.position)}
        if all(j in order for j in JOINTS):
            self.q = np.array([order[j] for j in JOINTS])

    def on_scan(self, msg):
        blocked = msg.ranges[0] < 0.4
        if blocked and not self.blocked and self.running:
            self.seen += 1
            name = min(self.boxes, key=lambda b: abs(self.boxes[b] - BARRIER_Y))
            self.tracked.append(name)
            self.log(f'barrera {name} vistas={self.seen}')
        self.blocked = blocked

    def place(self, name, x, y, z, orientation=None):
        state = EntityState(name=name, reference_frame='world')
        state.pose = Pose(position=Point(x=float(x), y=float(y), z=float(z)), orientation=orientation or Quaternion(w=1.0))
        self.set_state.call_async(SetEntityState.Request(state=state))

    def command(self, pose, seconds):
        msg = JointTrajectory(joint_names=JOINTS)
        whole = int(seconds)
        msg.points = [JointTrajectoryPoint(positions=[float(v) for v in pose],
                                           time_from_start=Duration(sec=whole, nanosec=int((seconds - whole) * 1e9)))]
        self.traj.publish(msg)

    def tool(self):
        T = fk(self.links, self.q)
        T[2, 3] += PEDESTAL_H
        return T

    def update_tool(self):
        """La pinza y la caja sujeta siguen la pose medida del brazo."""
        if self.q is None:
            return
        T = self.tool()
        q = Quaternion(**dict(zip('xyzw', mat_quat(T[:3, :3]))))
        self.place('pinza', *T[:3, 3], q)
        if self.carried:
            self.place(self.carried, T[0, 3], T[1, 3], T[2, 3] - GRIP_LEN - BOX_H, YAW_90)

    def advance_arm(self, running):
        if self.q is None:
            return
        if not running:
            if self.commanded is not None:
                self.command(self.q, 0.1)
                self.commanded = None
            return
        if self.step is None:
            if self.at_pick:
                self.step = 0
            return
        pose, seconds, action = CYCLE[self.step]
        target = self.poses[pose]
        if self.commanded != self.step:
            self.command(target, seconds)
            self.commanded = self.step
        if np.abs(self.q - target).max() < 0.01:
            if action == 'grasp':
                self.carried, self.at_pick = self.at_pick, None
                self.boxes.pop(self.carried)
                self.log(f'recoge {self.carried}')
            elif action == 'release':
                self.parked, self.carried = self.carried, None
                self.place(self.parked, *OUT_POS, OUT_TOP, YAW_90)
                self.produced += 1
                self.out.publish(UInt64(data=self.produced))
                self.log(f'deja {self.parked} producidas={self.produced}')
            elif action == 'done':
                self.waiting.append(self.parked)
                self.parked = None
            self.step = None if action == 'done' else self.step + 1

    def tick(self):
        now = time.monotonic()
        dt, self.tick_at = now - self.tick_at, now
        running = now - self.last_rx < self.deadline
        if running != self.running:
            self.running = running
            self.log('MARCHA' if running else 'PARO')
            on, off = LAMP[running]
            self.place(on, *LAMP_XY, LAMP_Z[on])
            self.place(off, *LAMP_XY, -1.0)
        self.advance_arm(running)
        self.update_tool()
        if not running:
            return
        if self.waiting and all(y - Y_IN > MIN_GAP for y in self.boxes.values()):
            self.boxes[self.waiting.pop(0)] = Y_IN
        if self.at_pick:
            return
        for name in self.boxes:
            self.boxes[name] += SPEED * dt
            self.place(name, CONV_X, self.boxes[name], BELT_TOP, YAW_90)
        if self.tracked and self.boxes[self.tracked[0]] >= PICK_Y:
            self.at_pick = self.tracked.pop(0)
        if any(y > Y_END for y in self.boxes.values()):
            raise RuntimeError('una caja pasó sin ser recogida')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--heartbeat', default='/mtbf/out_p3')
    p.add_argument('--deadline', type=float, default=0.5)
    a = p.parse_args()
    rclpy.init()
    node = Cell(a.heartbeat, a.deadline)
    while not node.set_state.wait_for_service(timeout_sec=1.0):
        pass
    rclpy.spin(node)


if __name__ == '__main__':
    main()
