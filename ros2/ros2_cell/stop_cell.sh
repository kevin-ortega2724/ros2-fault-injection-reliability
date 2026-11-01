#!/usr/bin/env bash
# Cierra la celda y los nodos de la demostración.
pkill -f 'python3 line_controller.py'
pkill -f 'python3 fault_demo.py'
pkill -f robot_state_publisher
pkill -f 'ros2_pilot/component.py'
pkill -x gzclient
pkill -x gzserver
sleep 3
pkill -9 -x gzserver
pkill -9 -f 'ros2_pilot/component.py'
exit 0
