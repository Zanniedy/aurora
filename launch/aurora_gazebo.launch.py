from datetime import datetime
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, GroupAction, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap


ROOT = Path(__file__).resolve().parents[1]


def validate_inputs(context):
    checkpoint = Path(LaunchConfiguration("checkpoint").perform(context)).expanduser()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    output = Path(LaunchConfiguration("output").perform(context)).expanduser()
    if output.exists():
        raise FileExistsError(f"Choose a new validation output directory: {output}")
    return []


def generate_launch_description():
    robot_launch = Path(get_package_share_directory("rm_9_2")) / "launch"
    return LaunchDescription([
        DeclareLaunchArgument("gui", default_value="true"),
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("render_backend", default_value="nvidia", choices=["auto", "nvidia", "system"]),
        DeclareLaunchArgument("checkpoint", default_value=str(ROOT / "runs/aurora_tunnel_v1/best.pt")),
        DeclareLaunchArgument("output", default_value=str(ROOT / "runs" / datetime.now().strftime("gazebo_%Y%m%d_%H%M%S"))),
        DeclareLaunchArgument("device", default_value="cpu"),
        DeclareLaunchArgument("rate", default_value="2"),
        DeclareLaunchArgument("orientation_frame", default_value="base_link"),
        OpaqueFunction(function=validate_inputs),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(robot_launch / "gazebo.launch.py")),
            launch_arguments={"gui": LaunchConfiguration("gui"), "run": "true",
                              "render_backend": LaunchConfiguration("render_backend")}.items(),
        ),
        TimerAction(period=3.0, actions=[GroupAction(actions=[
            SetRemap(src="/rm92/joint_states", dst="/joint_states"),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(str(robot_launch / "spawn_robots.launch.py"))),
        ])]),
        ExecuteProcess(
            cmd=["/usr/bin/python3", "-u", str(ROOT / "scripts/ros_infer.py"),
                 "--checkpoint", LaunchConfiguration("checkpoint"), "--output", LaunchConfiguration("output"),
                 "--device", LaunchConfiguration("device"), "--rate", LaunchConfiguration("rate"),
                 "--orientation-frame", LaunchConfiguration("orientation_frame"),
                 "--ros-args", "-p", "use_sim_time:=true",
                 "-r", "/tf:=/rm92/tf", "-r", "/tf_static:=/rm92/tf_static"],
            output="screen",
        ),
        TimerAction(period=5.0, actions=[Node(
            package="rviz2", executable="rviz2", name="aurora_rviz",
            arguments=["-d", str(ROOT / "configs/aurora_ros.rviz")],
            parameters=[{"use_sim_time": True}], condition=IfCondition(LaunchConfiguration("rviz")),
            remappings=[("/tf", "/rm92/tf"), ("/tf_static", "/rm92/tf_static")],
            output="screen",
        )]),
    ])
