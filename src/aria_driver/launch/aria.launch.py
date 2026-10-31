"""Start the aria node with one parameter file."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('aria_driver'), 'config', 'aria.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=config,
                              description='ROS parameter file of the aria node'),
        Node(package='aria_driver', executable='aria_node', name='aria', output='screen',
             parameters=[LaunchConfiguration('config')]),
    ])
