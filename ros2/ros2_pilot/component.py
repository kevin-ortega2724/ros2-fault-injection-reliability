"""Nodo ROS 2 genérico: fuente, relé con cuórum k-de-n o monitor."""
import argparse
import random
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt64

QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)


class Component(Node):
    def __init__(self, a):
        super().__init__(a.name)
        self.k, self.sink, self.last, self.votes = a.k, a.role == 'sink', 0, {}
        self.loss = a.loss
        self.pub = None if self.sink else self.create_publisher(UInt64, f'/mtbf/out_{a.name}', QOS)
        self.subs = [self.create_subscription(UInt64, f'/mtbf/out_{i}',
                                              lambda m, i=i: self.on_msg(m, i), QOS)
                     for i in a.inputs if i]
        if a.role == 'source':
            self.seq = 0
            self.create_timer(a.period, self.tick)

    def tick(self):
        self.seq += 1
        self.pub.publish(UInt64(data=self.seq))

    def on_msg(self, msg, source):
        if self.loss and random.random() < self.loss:
            return
        seq = msg.data
        if seq <= self.last:
            return
        voters = self.votes.setdefault(seq, set())
        voters.add(source)
        if len(voters) < self.k:
            return
        self.last = seq
        self.votes = {s: v for s, v in self.votes.items() if s > seq}
        if self.sink:
            print(time.monotonic(), flush=True)
        else:
            self.pub.publish(msg)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--name', required=True)
    p.add_argument('--role', choices=['source', 'relay', 'sink'], default='relay')
    p.add_argument('--inputs', default='')
    p.add_argument('--k', type=int, default=1)
    p.add_argument('--period', type=float, default=0.05)
    p.add_argument('--loss', type=float, default=0.0)
    a = p.parse_args()
    a.inputs = a.inputs.split(',')
    rclpy.init()
    rclpy.spin(Component(a))


if __name__ == '__main__':
    main()
