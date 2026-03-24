#!/usr/bin/env python3

# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os
import tempfile
import unittest

from diagnostic_msgs.msg import DiagnosticStatus
from greenwave_monitor.test_utils import (
    collect_diagnostics_for_topic,
    create_minimal_publisher,
    create_monitor_node,
    MONITOR_NODE_NAME,
    MONITOR_NODE_NAMESPACE,
)
import launch
import launch_testing
from launch_testing import post_shutdown_test
from launch_testing.asserts import assertExitCodes
import pytest
import rclpy
from rclpy.node import Node


_temp_dir = tempfile.TemporaryDirectory()

PRESET_TEST_TOPIC = '/preset_test_topic'

# (preset, message_type, expected_hz, publish_hz, tolerance_percent, expect_error, msg_substring)
FPS_OUT_OF_RANGE_NODE = 'FPS OUT OF RANGE (NODE TIME)'
PRESET_TEST_CASES = [
    ('header_with_nodetime_fallback', 'string', 100.0, 40.0, 30.0, True, FPS_OUT_OF_RANGE_NODE),
    ('header_only', 'string', 100.0, 40.0, 30.0, False, None),
    ('header_with_nodetime_fallback', 'image', 100.0, 100.0, 30.0, False, None),
    ('nodetime_only', 'image', 100.0, 40.0, 30.0, True, FPS_OUT_OF_RANGE_NODE),
    ('none', 'string', 100.0, 40.0, 30.0, False, None),
]


def create_preset_yaml(preset, expected_hz, tolerance_percent):
    """Create YAML config with gw_time_check_preset and frequency for PRESET_TEST_TOPIC."""
    yaml_content = f"""\
/**:
  ros__parameters:
    gw_time_check_preset: {preset}
    gw_frequency_monitored_topics:
      {PRESET_TEST_TOPIC}:
        expected_frequency: {expected_hz}
        tolerance: {tolerance_percent}
"""
    filepath = os.path.join(_temp_dir.name, f'preset_{preset}.yaml')
    with open(filepath, 'w') as f:
        f.write(yaml_content)
    return filepath


@pytest.mark.launch_test
@launch_testing.parametrize(
    'preset, message_type, expected_hz, publish_hz, tolerance_percent, '
    'expect_error, message_substring',
    PRESET_TEST_CASES
)
def generate_test_description(
    preset, message_type, expected_hz, publish_hz, tolerance_percent,
    expect_error, message_substring
):
    """Generate launch description for preset behavior tests."""
    yaml_config = create_preset_yaml(preset, expected_hz, tolerance_percent)

    ros2_monitor_node = create_monitor_node(
        namespace=MONITOR_NODE_NAMESPACE,
        node_name=MONITOR_NODE_NAME,
        parameters=[yaml_config, {'gw_monitored_topics': [PRESET_TEST_TOPIC]}]
    )

    publisher = create_minimal_publisher(
        PRESET_TEST_TOPIC, publish_hz, message_type, f'_{preset}_{message_type}'
    )

    context = {
        'preset': preset,
        'message_type': message_type,
        'expected_hz': expected_hz,
        'publish_hz': publish_hz,
        'tolerance_percent': tolerance_percent,
        'expect_error': expect_error,
        'message_substring': message_substring,
    }

    return (
        launch.LaunchDescription([
            ros2_monitor_node,
            publisher,
            launch_testing.actions.ReadyToTest()
        ]),
        context
    )


def find_status_for_topic(diagnostics, topic_name):
    """Return the most recent DiagnosticStatus for the given topic."""
    for status in reversed(diagnostics):
        if status.name == topic_name:
            return status
    return None


@post_shutdown_test()
class TestGreenwaveMonitorPresetPostShutdown(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.test_node = Node('preset_shutdown_test_node')

    @classmethod
    def tearDownClass(cls):
        cls.test_node.destroy_node()
        rclpy.shutdown()

    def test_node_shutdown(self, proc_info):
        available_nodes = self.test_node.get_node_names()
        self.assertNotIn(MONITOR_NODE_NAME, available_nodes)
        assertExitCodes(proc_info, allowable_exit_codes=[0])


class TestGreenwaveMonitorPreset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.test_node = Node('preset_test_node')

    @classmethod
    def tearDownClass(cls):
        cls.test_node.destroy_node()
        rclpy.shutdown()

    def test_preset_behavior(
        self, preset, message_type, expected_hz, publish_hz, tolerance_percent,
        expect_error, message_substring
    ):
        """Verify diagnostic level and message match expected preset behavior."""
        received = collect_diagnostics_for_topic(
            self.test_node, PRESET_TEST_TOPIC, expected_count=8, timeout_sec=20.0
        )

        self.assertGreaterEqual(
            len(received), 1,
            f'Expected at least one diagnostic for {PRESET_TEST_TOPIC}'
        )

        status = find_status_for_topic(received, PRESET_TEST_TOPIC)
        self.assertIsNotNone(
            status,
            f'No diagnostic status found for topic {PRESET_TEST_TOPIC}'
        )

        if expect_error:
            self.assertEqual(
                status.level, DiagnosticStatus.ERROR,
                f'Preset {preset}: expected ERROR, got level={status.level} msg={status.message}'
            )
            if message_substring:
                self.assertIn(
                    message_substring, status.message,
                    f'Preset {preset}: expected "{message_substring}" in "{status.message}"'
                )
        else:
            self.assertEqual(
                status.level, DiagnosticStatus.OK,
                f'Preset {preset}: expected OK, got level={status.level} msg={status.message}'
            )


if __name__ == '__main__':
    unittest.main()
