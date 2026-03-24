# Copyright (c) 2025-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
    )
    use_sim_time = LaunchConfiguration('use_sim_time')

    global_planner_arg = DeclareLaunchArgument(
        'global',
        default_value='false',
        description='If "true", monitor global-mode topics (graph MSF, SwiftNav, global planner) '
                    'in addition to local topics.',
    )
    global_planner = LaunchConfiguration('global')

    package_name = 'greenwave_monitor'

    config_file = PathJoinSubstitution([
        FindPackageShare(package_name), 'config', 'robot_b2w.yaml',
    ])

    global_config_file = PathJoinSubstitution([
        FindPackageShare(package_name), 'config', 'robot_b2w_global.yaml',
    ])

    greenwave_monitor_local = Node(
        package=package_name,
        executable='greenwave_monitor',
        name='greenwave_monitor',
        output='screen',
        parameters=[
            config_file,
            {'use_sim_time': use_sim_time},
        ],
        condition=IfCondition(PythonExpression(["'", global_planner, "' == 'false'"])),
    )

    greenwave_monitor_global = Node(
        package=package_name,
        executable='greenwave_monitor',
        name='greenwave_monitor',
        output='screen',
        parameters=[
            config_file,
            global_config_file,
            {'use_sim_time': use_sim_time},
        ],
        condition=IfCondition(global_planner),
    )

    return LaunchDescription([
        use_sim_time_arg,
        global_planner_arg,
        greenwave_monitor_local,
        greenwave_monitor_global,
    ])
