from launch import LaunchDescription
from launch.substitutions import EnvironmentVariable, PathJoinSubstitution
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():

    root = EnvironmentVariable("AURORA_ROOT", default_value=".")
    rose_nav_lm_node = ExecuteProcess(
        cmd=[
            PathJoinSubstitution([root, "build", "bin", "nav_lm"]),
            "--ros-args",
            "--params-file",
            PathJoinSubstitution([root, "config", "nav", "mid360_lm.yaml"]),
        ],
        output="screen",
    )
    static_base_link_to_livox_frame = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x",
            "0.0",
            "--y",
            "0.0",
            "--z",
            "0.0",
            "--roll",
            "0.0",
            "--pitch",
            "0.0",
            "--yaw",
            "0.0",
            "--frame-id",
            "base_link",
            "--child-frame-id",
            "livox_frame",
        ],
    )

    return LaunchDescription([rose_nav_lm_node, static_base_link_to_livox_frame])
