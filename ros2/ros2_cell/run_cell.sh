#!/usr/bin/env bash
# Abre la celda en Gazebo con el brazo UR5e y sus controladores. Generar antes con build_cell.py.
HERE="$(cd "$(dirname "$0")" && pwd)"
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-30} ROS_LOCALHOST_ONLY=1 GAZEBO_MODEL_DATABASE_URI=""
UR="$(ros2 pkg prefix ur_description)/share/ur_description"
export GAZEBO_MODEL_PATH="$HERE/models:$(dirname "$UR"):$GAZEBO_MODEL_PATH"
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat "$HERE/build/ur5e_control.urdf")" &
gazebo --verbose -s libgazebo_ros_init.so -s libgazebo_ros_factory.so "$HERE/build/cell.world" &
GZ=$!
ros2 run gazebo_ros spawn_entity.py -file "$HERE/build/ur5e_control.urdf" -entity ur5e -z 0.75 -timeout 60
ros2 run controller_manager spawner joint_state_broadcaster -c /controller_manager
ros2 run controller_manager spawner joint_trajectory_controller -c /controller_manager
wait $GZ
