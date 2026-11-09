# Gazebo / ROS 2 隧道验证

此入口独立于训练，只订阅点云/TF、发布预测与可视化，不发送 `/cmd_vel` 或导航目标，
不修改 `ray-sentry-ying-` 工作空间。不要重复启动已有的仿真。

## 启动

使用系统 Python（本机 `/usr/bin/python3` 已有 ROS Humble、NumPy、PyTorch），不要在 Isaac conda 环境中混装 ROS。

```bash
source /opt/ros/humble/setup.bash
source /home/lsy/cs_project/ray-sentry-ying-/install/setup.bash
ros2 launch /home/lsy/cs_project/aurora/launch/aurora_gazebo.launch.py
```

这是独立入口，直接复用机器人包的 Gazebo 与生成机器人组件，不经过 `cs_bringup`，
不启动 LIO、地图、拓扑规划、跟踪器。一起启动 Aurora 和专用 RViz；不需要编译 Aurora 为 ROS 包。
RViz 以 `base_link` 为固定坐标系，显示 `/rm92/robot_description` 机器人模型、原始点云和预测点，
因此是机器人局部视角，不依赖世界定位。`gui:=false` 可只保留 RViz，`rviz:=false` 可关闭 RViz。
机器人包中的关节/底盘控制和传感器桥接保留，但此入口不发移动指令。

如果已有仿真，只单独挂接推理（不要再启动上面的一键入口）：

```bash
cd /home/lsy/cs_project/aurora
source /opt/ros/humble/setup.bash
source /home/lsy/cs_project/ray-sentry-ying-/install/setup.bash
/usr/bin/python3 scripts/ros_infer.py \
  --checkpoint runs/aurora_tunnel_v1/best.pt \
  --output runs/gazebo_validation_01 \
  --ros-args -p use_sim_time:=true -r /tf:=/rm92/tf -r /tf_static:=/rm92/tf_static
```

节点启动时只加载一次权重并记录 SHA-256/训练轮次，不跟随训练中的 `best.pt` 更新。
默认 CPU、2 个线程、每次处理后至少间隔 0.5 秒；`--duration 60` 可做有限时长验证。
输出目录必须不存在，避免覆盖已有记录。退出用 Ctrl+C。可视化：

```bash
rviz2 -d /home/lsy/cs_project/aurora/configs/aurora_ros.rviz --ros-args -p use_sim_time:=true -r /tf:=/rm92/tf -r /tf_static:=/rm92/tf_static
```

也可在已有 RViz 添加 MarkerArray `/aurora/tunnel_markers`。
橙色球表示入口底边中点，文字表示置信度。默认不显示真值，也不代表已经验收通过。

视角操作：选择顶部 `Move Camera`，左键拖动旋转、中键拖动平移、滚轮缩放。
`Views` 面板可切换 `Orbit` 三维视角和 `TopDownOrtho` 俯视视角。

2026-11-09 首次静止出生点检查连续处理 232 帧，无超过默认阈值的检测；
该检查仅确认点云、推理和 RViz 链路已接通，不是检测精度验收，也没有降低阈值制造显示结果。

## 输入与坐标

- 输入 `/livox/lidar`，输出 `/aurora/tunnel_detections`（JSON String）、`/aurora/tunnel_markers`。
- 使用单帧有限 xyz，不使用累积地图、不使用世界位置作为网络输入。
- 该机器人的安装 RPY 为 `(0.67, 0, 0.78)` 弧度，而训练横滚仅 ±3°。
  默认读取点云时刻的 TF，将 xyz **仅旋转**到 `base_link` 方向，保持雷达原点，
  再推理；预测逆旋转回原始点云 frame，保留原始时间戳。不是把原点移到机器人中心。
- `base_link` 方向仅消除安装倾斜，机器人自身倾斜不会被消除。TF 不可用则跳过，不猜外参。
- `--orientation-frame ''` 可做未经校正的基线，不能将两者混作同一个实验。
- 校正无法补回原始扫描未覆盖的方向，也不能消除扫描密度、遮挡、安装高度等分布差异。

## 留存与判读

`session.json` 固定本次权重和配置；`predictions.jsonl` 保存每帧点数、时间戳、
坐标旋转、雷达坐标系预测和处理耗时；前 20 帧保存 NPZ（`xyz` 为模型输入，
`raw_xyz` 为原始雷达坐标）；`summary.json` 保存退出时的处理计数。

此步骤是另一种模拟传感器上的集成/域迁移检查，不是独立场地或真实雷达测试。
没有可见性真值标注前，不报告准确率、召回率或定位 MAE。静止出生点的重复帧也不算独立样本。
后续应由操作者在安全仿真中设置隧道外侧、斜视、背面和无隧道等位置，留存失败样例，
再核对 Gazebo 世界坐标真值与可见性，不能为让结果好看临时降低阈值。

Gazebo 场地坐标与 Aurora 居中坐标相差 `(6.3, 4.3, 0)` 米；
这来自两边对同一 STL 的导入变换，不能直接把 Gazebo `world` 当作 LIO `map`。
