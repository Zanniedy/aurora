from launch import LaunchDescription
from launch.substitutions import EnvironmentVariable, PathJoinSubstitution
from launch.actions import ExecuteProcess


def generate_launch_description():

    root = EnvironmentVariable("AURORA_ROOT", default_value=".")
    rose_nav_map_node = ExecuteProcess(
        cmd=[
            PathJoinSubstitution([root, "build", "bin", "nav_map"]),
            "--ros-args",
            "--params-file",
            PathJoinSubstitution([root, "config", "nav", "rose_map.yaml"]),
        ],
        output="screen",
    )
  

    return LaunchDescription([rose_nav_map_node])
