"""Escucha las salidas de todos los componentes e imprime nombre y hora de cada mensaje."""
import sys
import time

import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt64

rclpy.init()
node = rclpy.create_node('probe')
qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
for name in sys.argv[1].split(','):
    node.create_subscription(UInt64, f'/mtbf/out_{name}', lambda _m, n=name: print(n, time.monotonic(), flush=True), qos)
rclpy.spin(node)
