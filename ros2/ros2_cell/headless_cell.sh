#!/usr/bin/env bash
# Celda sin interfaz: headless_cell.sh <dominio> <puerto_gazebo>; la cierra quien la lanzó, por grupo de procesos.
HERE="$(cd "$(dirname "$0")" && pwd)"
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=$1 ROS_LOCALHOST_ONLY=1 GAZEBO_MODEL_DATABASE_URI="" GAZEBO_MASTER_URI=http://127.0.0.1:$2
UR="$(ros2 pkg prefix ur_description)/share/ur_description"
export GAZEBO_MODEL_PATH="$HERE/models:$(dirname "$UR"):$GAZEBO_MODEL_PATH"
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat "$HERE/build/ur5e_control.urdf")" >/dev/null 2>&1 &
gzserver -s libgazebo_ros_init.so -s libgazebo_ros_factory.so "$HERE/build/cell.world" >/dev/null 2>&1 &
ros2 run gazebo_ros spawn_entity.py -file "$HERE/build/ur5e_control.urdf" -entity ur5e -z 0.75 -timeout 120 >/dev/null 2>&1
ros2 run controller_manager spawner joint_state_broadcaster -c /controller_manager --controller-manager-timeout 60 >/dev/null 2>&1
ros2 run controller_manager spawner joint_trajectory_controller -c /controller_manager --controller-manager-timeout 60 >/dev/null 2>&1
echo READY
wait
