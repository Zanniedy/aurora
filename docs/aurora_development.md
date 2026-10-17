# Aurora 项目开发与二次开发文档

本文档对应当前仓库 `/home/lsy/cs_project/aurora`，用于说明迁移后的雷达、哨兵、自瞄、能量机关和导航代码如何构建、启动、调试和二次开发。

## 1. 项目定位

Aurora 是一个单体 CMake 工程，当前包含以下能力：

- 哨兵自瞄：相机采集、装甲板检测、数字分类、目标跟踪、弹道解算和云台控制。
- 能量机关：能量机关检测、跟踪、预测和控制。
- 哨兵决策：串口状态接收、模式切换、地图点位和导航目标管理。
- 雷达站：海康相机、TensorRT 检测、点云定位、车辆跟踪、裁判系统和无线链路。
- 导航：Small-Point-LIO 定位、占用栅格、ESDF、A*、MINCO 和 LMPC 控制。
- 配套工具：Livox V1 驱动、雷达标定、地图点位编辑、配置探针和 systemd 启动脚本。

当前工程已经从原来的多个工程组织方式合并为一个 CMake 工程。ROS 2 仍然作为运行时依赖使用，但不再要求通过 `colcon` 编译本仓库。

## 2. 快速开始

### 2.1 基础环境

推荐环境：

- Ubuntu 22.04。
- ROS 2 Humble。
- GCC 11 或更高版本，支持 C++23。
- Eigen3、OpenCV、yaml-cpp、TBB、Ceres、Boost、PCL、OSQP、OsqpEigen。
- 导航和建图需要 ROS 2 消息包、`tf2_ros`、`pcl_conversions` 等。

如果当前终端激活了 Conda，建议先执行：

```bash
source ./make.sh
```

`make.sh` 会尝试退出 Conda 环境、加载 ROS 2 Humble，并建立编译数据库。也可以手动加载 ROS：

```bash
source /opt/ros/humble/setup.bash
```

### 2.2 默认构建

默认构建自瞄、能量机关、导航和工具，但不构建雷达站，不启用 OpenVINO 和 TensorRT：

```bash
./run.sh build
```

等价的显式命令：

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DAURORA_BUILD_RADAR=OFF \
  -DAURORA_WITH_OPENVINO=OFF \
  -DAURORA_WITH_TRT=OFF
cmake --build build --parallel 4
```

所有可执行文件输出到 `build/bin/`。

### 2.3 运行配置探针

在没有 OpenVINO 的机器上，先运行配置探针确认 YAML 和主模型路径：

```bash
./run.sh run auto_aim_probe config/sentry.yaml
```

注意：探针只验证配置可读和主模型文件存在，不会真正初始化 OpenVINO、相机或串口。

### 2.4 实际运行自瞄

当前 `config/sentry.yaml` 默认使用 OpenVINO，因此正式运行前需要打开 OpenVINO 构建：

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DAURORA_WITH_OPENVINO=ON \
  -DAURORA_WITH_TRT=OFF \
  -DAURORA_BUILD_RADAR=OFF
cmake --build build --parallel 4
export AURORA_ROOT="$PWD"
./run.sh run auto_aim sentry true
```

`auto_aim` 第一个参数既可以写机器人别名，也可以写 YAML 路径：

```bash
./run.sh run auto_aim sentry false
./run.sh run auto_aim config/sentry.yaml true
```

第二个参数为 `true` 时启用调试数据路径和调试输出。实际硬件运行时通常使用 `false`，避免高频图像显示影响实时性。

## 3. 目录结构

```text
aurora/
├── CMakeLists.txt              # 单体工程入口和构建开关
├── run.sh                      # 构建、运行、gdb 包装脚本
├── make.sh                     # 加载环境并构建
├── config/                     # 自瞄、雷达、导航和地图配置
├── model/                      # 自瞄、能量机关模型及备用模型
├── data/                       # PCD、栅格地图、雷达模型和标定资料
├── launch/nav/                 # 导航 launch 文件
├── auto_start/                 # systemd 启动脚本
├── script/                     # 环境、同步、标定和模型导出脚本
├── src/auto_sentry/            # 哨兵、自瞄、能量机关、雷达和决策
├── src/navigation/             # LIO、地图、规划和控制
├── src/runtime/                # 各个可执行程序的 main
├── src/utils/                  # 相机、串口、调度器、日志和基础 IO
├── src/rcl/                    # ROS 2 节点和 TF 薄封装
├── src/mapper/                 # 建图相关接口
└── src/party/others/           # TinyMPC、滤波器、点云和其他第三方代码
```

## 4. 模块职责和数据流

### 4.1 自瞄数据流

自瞄主循环在 `src/runtime/auto_aim.cpp`，处理链路如下：

```text
相机/仿真共享内存
        ↓
ArmorDetector
  ├─ 传统灯条候选提取
  ├─ 神经网络装甲板检测
  ├─ 数字分类和颜色分类
  └─ 装甲板几何过滤
        ↓
ArmorTracker
  ├─ 目标匹配
  ├─ ES-EKF 状态估计
  ├─ 目标运动模型
  └─ 目标选择
        ↓
VeryAimer / BallisticTrajectory
  ├─ 坐标变换
  ├─ 重力和空气阻力补偿
  ├─ 延迟补偿
  └─ 目标装甲板选择
        ↓
AutoAimFsmController
        ↓
串口发送云台和发射控制量
```

关键代码位置：

- `src/auto_sentry/aim/armor_detect/armor_detector.*`：检测入口、候选过滤和分类。
- `src/auto_sentry/aim/armor_detect/armor_infer.*`：装甲板神经网络输出解析。
- `src/auto_sentry/aim/armor_track/armor_tracker.*`：目标匹配和跟踪器。
- `src/auto_sentry/aim/armor_track/armor_target.*`：目标状态、装甲板选择和预测数据。
- `src/auto_sentry/aim/armor_control/very_aimer.*`：最终瞄准、弹道和控制量计算。
- `src/auto_sentry/aim/auto_aim_fsm.hpp`：搜索、跟踪、丢失、瞄准等状态机。
- `src/auto_sentry/base/ballistic_trajectory.hpp`：弹道模型。
- `src/party/others/tinympc/` 和 `dual_small_mpc_solver.hpp`：MPC 相关求解器。

### 4.2 能量机关数据流

当 `config/sentry.yaml` 的 `mode` 为 `auto_buff` 时，主程序会使用：

```text
相机帧 → RuneDetector → RuneTracker → RuneAimer → 串口控制
```

对应代码：

- `src/auto_sentry/buff/rune_detect/`：能量机关检测和推理。
- `src/auto_sentry/buff/rune_track/`：运动模型、目标状态和跟踪。
- `src/auto_sentry/buff/rune_control/rune_aimer.*`：预测击打时机和控制量。
- `src/auto_sentry/buff/type.hpp`：能量机关数据类型。

### 4.3 雷达站数据流

雷达检测进程位于 `src/runtime/radar_detect.cpp`，整体链路为：

```text
海康相机
   ↓
车辆检测 + 装甲板检测
   ↓
像素到世界坐标 / 点云定位
   ↓
车辆跟踪和 CarPool
   ↓
地图匹配、己方/敌方信息整理
   ↓
裁判系统或无线串口发送
```

雷达核心代码位于 `src/auto_sentry/radar/`：

- `detector.*`：TensorRT 检测封装。
- `lidar_location.*`：点云定位和聚类。
- `tracker.hpp`、`car_pool.hpp`：车辆跟踪和生命周期管理。
- `pixel_to_world.hpp`：相机像素到地图坐标转换。
- `livox_v1/`：Livox V1 UDP 数据解析和 ROS 2 发布。
- `io/`：协议帧和 CRC。

### 4.4 导航数据流

导航由三个独立进程组成：

```text
Livox/ROS 点云 + IMU
        ↓
nav_lm / Small-Point-LIO
        ↓ 里程计和 TF
nav_map / OccMap + BinMap + ESDF
        ↓ 地图和障碍物
nav_planner / A* + MINCO + LMPC
        ↓ /cmd_vel
sentry_nav / 串口转发或哨兵决策
```

对应代码：

- `src/navigation/lm/`：Small-Point-LIO、ESKF、IMU 和点云适配。
- `src/navigation/map/`：占用图、二值地图、ESDF 和静态地图。
- `src/navigation/planner/`：A*、轨迹优化、LMPC 和规划节点。
- `src/runtime/nav_lm.cpp`、`nav_map.cpp`、`nav_planner.cpp`：三个独立入口。
- `src/runtime/sentry_nav.cpp`：串口收发、`/cmd_vel` 转发和可选决策脑。

## 5. 模型清单

模型文件分为“当前默认配置引用”“可替换后端格式”和“历史/实验候选”三类。未被当前 YAML 引用的模型不应直接替换线上模型，需先确认输入尺寸、类别顺序和输出格式。

### 5.1 当前配置正在使用

| 文件 | 用途 | 当前引用位置 | 状态 |
|---|---|---|---|
| `model/opt-1208-001.onnx` | 装甲板主检测，输出装甲板候选和类别信息 | `config/sentry.yaml` 的 `armor_detector.net_detector.openvino` | 默认启用 |
| `model/mlp.onnx` | 装甲板数字分类，识别 `1` 至 `5`、`outpost`、`guard`、`base`、`negative` | `config/sentry.yaml` 的 `number_classifier` | 默认启用 |
| `model/label.txt` | 数字分类输出索引到类别名的映射 | `number_classifier.label_path` | 默认启用 |
| `model/cb_rune.onnx` | 能量机关检测 | `config/sentry.yaml` 的 `rune_detector.net_detector.openvino` | `auto_buff` 时启用 |
| `data/radar/Horizon-Car-yolov8s-ghost-p2-2026-04-06.onnx` | 雷达车辆检测 | `config/radar.yaml` 的 `detector.car.model_path` | 雷达启用时使用 |
| `data/radar/Horizon-Armor-yolov8n-ghost-p2-2026-04-04.onnx` | 雷达装甲板检测 | `config/radar.yaml` 的 `detector.armor.model_path` | 雷达启用时使用 |

雷达的 TensorRT 代码当前从 ONNX 构建推理引擎；旁边的 `.engine` 文件属于预生成备份，不代表当前程序一定会自动加载它。

### 5.2 已迁移的备用格式

| 文件 | 作用和关系 | 使用说明 |
|---|---|---|
| `model/opt-1208-001.engine` | `opt-1208-001.onnx` 的 TensorRT 序列化版本 | 需要改 TensorRT 后端加载逻辑后使用 |
| `model/opt-1208-001.bin` + `model/opt-1208-001.param` | `opt-1208-001` 的 NCNN 转换版本 | 两个文件必须成对使用 |
| `model/opt_1208_001.ncnn.bin` + `model/opt_1208_001.ncnn.param` | 同一装甲板模型的另一套 NCNN 命名版本 | 当前没有 NCNN 运行时入口 |
| `model/cb_rune.engine` | `cb_rune.onnx` 的 TensorRT 版本 | 当前能量机关默认配置使用 OpenVINO ONNX |
| `data/radar/Horizon-Car-yolov8s-ghost-p2-2026-04-06.engine` | 雷达车辆检测 TensorRT 引擎 | 当前配置仍指向 ONNX |
| `data/radar/Horizon-Armor-yolov8n-ghost-p2-2026-04-04.engine` | 雷达装甲板检测 TensorRT 引擎 | 当前配置仍指向 ONNX |

### 5.3 历史/实验候选模型

以下文件已经随工程迁移，但当前配置没有引用。仓库没有保存完整训练元数据，因此只能根据文件名和现有代码用途做候选分类，二次开发时必须用验证集重新确认：

| 文件 | 推测用途 | 当前状态 |
|---|---|---|
| `model/0526.onnx`、`model/0526.engine` | 装甲板检测候选模型及 TensorRT 版本 | 未启用 |
| `model/0708.onnx`、`model/0708.engine` | 装甲板检测候选模型及 TensorRT 版本 | 未启用 |
| `model/opt-0527-001.onnx` | 装甲板检测候选模型 | 未启用 |
| `model/praysky_c2psa_e2e_0228_576x768.onnx`、`.engine` | 端到端装甲板检测候选模型，输入尺寸名为 `576x768` | 未启用 |
| `model/praysky_c2psa_e2e_0228_640x640.onnx`、`.engine` | 端到端装甲板检测候选模型，输入尺寸名为 `640x640` | 未启用 |
| `model/mlp_finetuned.onnx` | 数字分类器微调候选版本 | 未启用 |
| `model/lenet.onnx` | 数字分类器候选版本 | 未启用 |
| `model/reborn_number_classifier.onnx`、`.engine` | 数字分类器候选模型及 TensorRT 版本 | 未启用 |
| `model/tiny_resnet.onnx` | 轻量数字/类别分类候选模型 | 未启用 |

更换模型时，除了修改 `model_path`，还要检查以下内容：输入尺寸、BGR/RGB 顺序、归一化方式、输出张量格式、类别索引、置信度阈值和后处理代码。装甲板检测输出解析在 `armor_infer.cpp`，能量机关输出解析在 `rune_infer.cpp`，不能只替换文件名。

## 6. 可执行程序和启动方式

### 6.1 自瞄和能量机关

| 程序 | 作用 | 启动命令 |
|---|---|---|
| `auto_aim` | 实际运行自瞄或能量机关主循环 | `./run.sh run auto_aim sentry false` |
| `auto_aim_probe` | 检查配置和主模型路径 | `./run.sh run auto_aim_probe config/sentry.yaml` |
| `sentry_nav` | 串口状态、`/cmd_vel` 转发和可选决策 | `./run.sh run sentry_nav config/sentry.yaml` |
| `sentry_nav` + brain | 启用哨兵决策模式 | `./run.sh run sentry_nav config/sentry.yaml brain` |
| `map_edit` | 从 ROS 地图生成哨兵点位配置 | `./run.sh run map_edit data/nav/map/rmuc_2024.yaml config/rmuc_2026_map_point.yaml` |

`sentry_nav` 的配置需要包含 `serial` 和 `brain` 节点，实际机器人应使用对应车辆配置；当前仓库默认提供的完整视觉配置是 `config/sentry.yaml`。

### 6.2 雷达站

雷达构建需要 Open3D；启用 TensorRT 后才会生成 `radar_detect`：

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DAURORA_BUILD_RADAR=ON \
  -DAURORA_WITH_TRT=ON \
  -DAURORA_WITH_OPENVINO=OFF
cmake --build build --parallel 4
```

启动方式：

```bash
# Livox V1 数据发布
./run.sh run livox_v1_driver config/radar.yaml

# 雷达检测、定位、跟踪和发送
./run.sh run radar_detect config/radar.yaml

# 雷达标定工具：1 地图点位，2 保存图片，3 标注框
./run.sh run radar_cal config/radar.yaml 1
./run.sh run radar_cal config/radar.yaml 2
./run.sh run radar_cal config/radar.yaml 3
```

雷达默认配置已改为海康相机。离线视频测试时，将 `config/radar.yaml` 的 `camera.type` 改为 `video`，并把 `camera.video.path` 改为本机存在的视频文件。

### 6.3 导航

先加载 ROS 2 并完成构建：

```bash
source /opt/ros/humble/setup.bash
./run.sh build
```

推荐分三个终端启动：

```bash
# 终端 1：LIO 定位
./run.sh run nav_lm --ros-args --params-file config/nav/mid360_lm.yaml

# 终端 2：地图、占用栅格和 ESDF
./run.sh run nav_map --ros-args --params-file config/nav/rose_map.yaml

# 终端 3：路径规划和 LMPC
./run.sh run nav_planner --ros-args --params-file config/nav/rose_planner.yaml
```

也可以使用 `launch/nav/` 下的 launch 文件作为 ROS 2 启动描述。它们通过 `AURORA_ROOT` 查找 `build/bin` 和 `config/nav`，启动前执行：

```bash
export AURORA_ROOT="$PWD"
```

当前仓库是单体 CMake 工程，没有安装为带 `package.xml` 的 ROS 2 package，因此最稳定的方式仍是上面的三个 `./run.sh run ...` 命令；launch 文件主要用于后续接入 ROS 2 package 或由现有 launch 系统加载。

导航的三个配置文件中使用 `${ROOT_DIR}`，`ParamsNode` 会优先使用环境变量 `AURORA_ROOT` 展开路径。

### 6.4 gdb 调试

`run.sh` 支持直接进入 gdb：

```bash
./run.sh debug auto_aim_probe config/sentry.yaml
./run.sh debug nav_lm --ros-args --params-file config/nav/mid360_lm.yaml
```

## 7. CMake 开关和依赖

| 选项 | 默认值 | 作用 |
|---|---:|---|
| `AURORA_BUILD_RADAR` | `OFF` | 构建 Open3D 雷达模块、Livox 驱动和标定程序 |
| `AURORA_WITH_OPENVINO` | `OFF` | 构建 OpenVINO 自瞄/能量机关后端 |
| `AURORA_WITH_TRT` | `OFF` | 构建 TensorRT 后端和雷达检测程序 |

相机 SDK 为可选发现：

- 海康 MVS：设置 `MVCAM_SDK_PATH`，通常为 `/opt/MVS`。
- 大恒：设置 `DAHENG_SDK_PATH`，具体取决于 SDK 安装位置。
- 迈德威视：设置 `MVSDK_PATH`。

`run.sh` 会设置常用的海康运行库路径，但不会替用户安装 SDK。没有对应 SDK 时，代码仍可编译不依赖该 SDK 的目标；运行对应相机类型会报未启用。

## 8. 配置二次开发指南

### 8.1 自瞄配置

主要文件：`config/sentry.yaml`。

- `mode`：`auto_aim` 或 `auto_buff`。
- `enemy_color`：敌方颜色，必须和比赛设置一致。
- `bullet_speed`：弹速，直接影响弹道解算。
- `serial`：串口设备、波特率和开关。
- `camera`：相机类型、设备序列号、分辨率、曝光和内参。
- `armor_detector`：后端、检测阈值、数字分类和颜色分类。
- `armor_tracker`：丢失时间、匹配门限、过程噪声和观测噪声。
- `very_aimer`：目标选择、延迟补偿、弹道参数和控制参数。
- `rune_detector`、`rune_tracker`、`rune_aimer`：能量机关链路参数。
- `tf`：相机、云台、枪口和底盘之间的外参。

修改顺序建议：相机内参/外参 → 弹速和延迟 → 检测阈值 → 跟踪门限 → 控制参数。不要在检测不稳定时直接调 MPC，否则问题会被控制环节放大。

### 8.2 雷达配置

主要文件：`config/radar.yaml`。

- `tf.camera_cv_in_target_map`：相机到目标地图坐标系的外参。
- `detector`：车辆和装甲板模型、阈值和 CUDA 预处理开关。
- `pixel_to_world.mesh_path`：雷达场地网格。
- `map.map_path`：俯视地图图片。
- `map.guess_path`：地图点位初值。
- `lidar_location.target_map_path`：目标点云地图。
- `tracker`：数据关联和目标生命周期。
- `referee_serial`、`wifi_serial`：裁判系统和无线串口。
- `camera`：实机相机或离线视频输入。

### 8.3 导航配置

- `config/nav/mid360_lm.yaml`：点云话题、IMU 话题、初始 PCD、雷达外参和 ESKF 参数。
- `config/nav/rose_map.yaml`：静态栅格地图、占用概率、体素大小和 ESDF 范围。
- `config/nav/rose_planner.yaml`：机器人半径、A* 权重、轨迹优化和 MPC 限制。

更换地图时同时检查 `static_map_path`、地图 YAML 中的 PGM 相对路径、地图坐标原点和 `mid360_lm.yaml` 的先验 PCD。只替换 PGM 而不检查原点，通常会造成定位和规划坐标错位。

## 9. 常见二次开发流程

### 9.1 更换自瞄模型

1. 确认模型输入尺寸、颜色通道和预处理。
2. 把模型放到 `model/`。
3. 修改 `config/sentry.yaml` 中对应 `model_path`。
4. 若输出格式变化，修改 `armor_infer.cpp` 或 `rune_infer.cpp`。
5. 保持 `model_type`、类别数和 `label.txt` 一致。
6. 先运行 `auto_aim_probe`，再用离线视频验证检测数量和类别。
7. 最后才接入串口和真实发射控制。

### 9.2 更换相机

1. 选择 `hik`、`daheng`、`mv`、`uvc` 或 `video`。
2. 设置相机 SDK 环境变量并重新 CMake 配置。
3. 修改曝光、分辨率、像素格式和相机内参。
4. 重新标定 `camera_info` 和相机到云台外参。
5. 先运行只采图的调试流程，再启用检测和控制。

### 9.3 更换串口

修改 `config/sentry.yaml` 或 `config/radar.yaml` 中的 `device_name`、`baud_rate` 和 `read_buf_size`。建议优先使用稳定的 `/dev/serial/by-id/` 或通过 `script/setup_udev.sh` 创建固定软链接，不要依赖 `/dev/ttyACM0` 的枚举顺序。

### 9.4 更换导航地图

1. 准备新的 PGM/YAML 栅格地图和 PCD 点云。
2. 将资源放入 `data/nav/map/` 和 `data/nav/pcd/`。
3. 修改 `rose_map.yaml`、`rose_planner.yaml` 的 `static_map_path`。
4. 修改 `mid360_lm.yaml` 的 `prior_pcd_path` 和初始位姿。
5. 校验 `map`、`odom`、`base_footprint` 和 `front_mid360` TF 方向。
6. 分别启动 LIO、地图和规划，最后再启动 `sentry_nav`。

### 9.5 增加新运行模块

1. 在 `src/runtime/` 增加独立 `main`。
2. 在对应子目录的 CMake 目标中声明依赖。
3. 使用 `aurora_add_executable`，使产物进入 `build/bin/`。
4. 如果需要 ROS 参数，复用现有 `--ros-args --params-file` 方式。
5. 在本文档“可执行程序和启动方式”中补充启动命令。

## 10. 脚本说明

- `run.sh build`：配置并编译。
- `run.sh rebuild`：删除 `build/` 后重新配置编译。
- `run.sh run <target> [args...]`：运行目标程序。
- `run.sh debug <target> [args...]`：通过 gdb 运行。
- `make.sh`：加载 ROS、退出 Conda 并构建。
- `script/rsync.sh <user> <ip> [remote_dir]`：同步源码、模型、数据和配置到远程机器，默认目录为远程用户家目录下的 `aurora`。
- `script/setup_udev.sh`：安装 STM32 串口固定软链接规则。
- `script/setup_devenv.sh`：向 shell 环境添加 Aurora 开发辅助函数。
- `script/export_gcn2_onnx.py`：将旧版 GCNv2 TorchScript archive 转换为 ONNX，必须显式传入 `--pt` 和 `--onnx`。
- `data/radar/cal.py`、`get_pts.py`、`objorigin.py`：雷达标定和点位处理辅助脚本。
- `auto_start/*.sh`：systemd 管理入口。旧的 `hero`、`leg`、`omni`、`uav`、`dong` 名称保留为兼容别名，默认都运行当前 `auto_aim` 和 `config/sentry.yaml`；要使用不同配置，设置 `AURORA_CONFIG=/绝对路径/配置.yaml`。

例如：

```bash
AURORA_CONFIG="$PWD/config/sentry.yaml" ./auto_start/sentry.sh install
sudo systemctl status aurora-auto-aim-sentry.service
sudo journalctl -u aurora-auto-aim-sentry.service -f
```

## 11. 故障排查

### 找不到模型或路径仍指向旧机器

确认环境变量和路径：

```bash
export AURORA_ROOT="$PWD"
./run.sh run auto_aim_probe config/sentry.yaml
```

配置中的 `${ROOT_DIR}` 由自瞄模型加载器或导航 `ParamsNode` 展开。不要把个人机器的绝对路径提交到 YAML。

### OpenVINO 后端不可用

现象通常是找不到 `openvino::runtime`、后端未编译或设备名称不匹配。检查：

1. 是否用 `-DAURORA_WITH_OPENVINO=ON` 重新配置。
2. 是否安装 OpenVINO Runtime 和 ONNX 前端。
3. `device_name` 是否为当前机器支持的 `CPU` 或 `GPU`。
4. 模型是否为有效 ONNX 文件。

### TensorRT 雷达目标没有生成

检查 `AURORA_BUILD_RADAR=ON`、`AURORA_WITH_TRT=ON`、CUDA、TensorRT、Open3D 和 `FindTensorRT.cmake`。只有开启 TensorRT 时，`build/bin/radar_detect` 才会生成。

### 相机打不开

- 检查 `camera.type` 是否和实际 SDK 一致。
- 检查对应 SDK 的环境变量和 `LD_LIBRARY_PATH`。
- 检查序列号、设备权限、像素格式和分辨率。
- 视频模式必须确认 `camera.video.path` 指向存在的视频文件。
- UVC 相机优先使用 `/dev/v4l/by-path/` 或 `/dev/v4l/by-id/`。

### 导航没有输出或坐标漂移

按以下顺序检查：

1. 点云和 IMU 话题是否有数据。
2. `lidar_frame`、`base_frame`、`sensor_frame` 是否统一。
3. `extrinsic_T` 和 `extrinsic_R` 的方向是否正确。
4. 先验 PCD 是否与当前场地一致。
5. 地图 YAML 的原点、分辨率和 PGM 文件是否匹配。
6. 规划器的 `target_frame`、里程计话题和 `/rose_goal` 是否一致。

### systemd 服务启动即退出

```bash
sudo systemctl status aurora-auto-aim-sentry.service
sudo journalctl -u aurora-auto-aim-sentry.service -n 200 --no-pager
```

重点检查服务里的 `WorkingDirectory`、`ExecStart`、模型路径、SDK 动态库和串口权限。systemd 不会自动继承交互式终端中的所有环境变量，必要时在服务文件中显式增加 `Environment=`。

## 12. 当前已知边界

- 默认构建关闭 OpenVINO 和 TensorRT，原因是这些依赖与目标机器 GPU/驱动强相关。
- `config/sentry.yaml` 默认 backend 是 OpenVINO，正式运行需按本文档重新配置构建。
- `src/auto_sentry/aim/experimental/` 是旧实验实现，仅供对照，不参与默认构建。
- `src/auto_sentry/base/web.hpp` 当前提供轻量兼容接口，日志和核心流程可用，完整 Web 可视化接口仍需后续接入。
- 未被当前 YAML 引用的历史模型没有完整训练说明，使用前必须进行离线回放和输出格式核验。
