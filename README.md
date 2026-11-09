# Aurora

单帧点云隧道入口检测项目：输入雷达 XYZ 点云，输出 `tunnel`、入口底边中点和置信度。
包含按手册尺寸核对的场地、几何射线采集、数据检查、体素 BEV 模型、训练、评估、推理和只读监控，
以及独立的 Gazebo / ROS 2 / RViz 验证入口。模型训练由用户手动启动。

训练采集使用 MID360 视场近似，不是精确 MID360 扫描模型或 Isaac RTX 传感器输出。
Gazebo 接入已经运行，但同场地仿真验证不代表真实雷达检测效果，参见 `docs/SIM_VALIDATION.md`。

## 仓库内容与前提

- 版本控制包含源码、配置、文档、场地 USD 和尺寸审计；不包含数据集、训练日志或模型权重。
- 最佳权重的默认本地路径为 `runs/aurora_tunnel_v1/best.pt`，续训权重为同目录的 `last.pt`。
  新克隆的仓库需要自行采集并训练，或另行取得权重，不能直接启动带模型的验证。
- 训练/采集使用本机 `isaaclab` 环境；ROS 接入使用系统 Python。不要将两套环境混装。
- 训练侧依赖 PyTorch、NumPy、TensorBoard；采集另外使用 Warp 和 USD Python API；
  数据预览使用 Pillow，场景窗口使用 Isaac Sim。
- Gazebo 验证依赖已构建的外部机器人工作空间及其中的 `rm_9_2`、传感器和控制插件，
  以及 ROS 2 Humble、RViz 和可用的系统 Python PyTorch。这些不随本仓库分发。
- 文档中的 `/home/lsy/...` 是本机示例路径。换电脑时调整环境与机器人工作空间路径；
  重新导入 STL 可用 `python scripts/build_scene.py --stl /实际路径/rmul_2027.stl`。

流程说明：数据格式见 `docs/DATASET.md`，训练见 `docs/TRAINING.md`，在线仿真见 `docs/SIM_VALIDATION.md`。

## 第一阶段训练范围

仅一个检测类别：`tunnel`（隧道）。输入为 MID360 的单帧点云，输出为隧道类别、位置和置信度。
高地、台阶、围墙及其余场地结构保留为真实背景，不设置为当前阶段的检测类别，也不删除这些遮挡结构。
位置参考点采用入口底边中点，同一隧道两端用不同 `entrance_id` 区分，只监督可观测、朝向传感器的入口。
采集器根据开口探测射线和结构回波数量筛选有效标注；不确定入口标为忽略。此自动可见性规则仍需人工抽检。
窗口默认使用 `Tunnel` 相机；需要全场视角时运行 `python scripts/preview_scene.py --gui --camera Overview`。

## 来源与尺寸核对

- 场地：`/home/lsy/Downloads/rmul_2027.stl`，3811 个三角面。模型来源由用户提供，未另外验证其发布者。
- 手册：`RoboMaster 2027 机甲大师高校联盟赛比赛规则手册 V1.0.0（20261015）.pdf`。
- 手册印刷页 24 / PDF 第 25 页，图 3-5：整体场内尺寸和布局。
- 手册印刷页 25 / PDF 第 26 页，图 3-8：高地、侧挡条和金属板下方隧道的尺寸。
- 手册印刷页 26 / PDF 第 27 页，图 3-9：隧道增益点位置，不是另一份隧道尺寸图。

**下列关键尺寸与手册标称值一致，按原始 STL 建模，不凭空添加或改变结构。**
这不是对全部制造细节的工程验收，也不等于已对比赛现场逐项实测。

| 检查项 | 手册标称值（mm） | STL 实测值（mm） |
| --- | ---: | ---: |
| 场内长 × 宽 | 12000 × 8000 | 12000 × 8000 |
| 单侧高地主体宽 × 长 | 2000 × 4060 | 2000 × 4060 |
| 高地面离地高度 | 200 | 200 |
| 侧挡条顶面离地高度 | 400 | 400 |
| 侧挡条宽 × 长 | 150 × 1800 | 150 × 1800 |
| 隧道通道净宽 | 800 | 800 |
| 金属板宽 | 350 | 350 |
| 隧道净高 | 250 | 250 |
| 金属板中央顶面离地高度 | 270 | 270 |

两侧隧道高度均经过核对。STL 源坐标中向上为 **−Y**，地面 Y=420，底板下表面 Y=520，
金属板中央底面 Y=170、顶面 Y=150，因此净高为 250 mm、板顶高度为 270 mm。
导入器通过水平面的法线方向和面积核对地面，不能仅凭最短包围盒轴假定其正方向朝上。
手册中高地与侧挡条的两处 200 mm 也不是两级等宽楼梯，不再保留概念版楼梯。

导入器**不修改原 STL**，也不擅自移动金属板。只做等比例单位换算与刚体坐标变换。
**以手册为准：隧道净高必须为 250 mm。** 核对表中的任一标称尺寸不一致时，导入器写出审计报告并拒绝生成场景，不静默接受偏差。
手册印刷页 21 还说明制造误差和未标注细节以实物为准；图纸标称尺寸不等同于已实测的现场尺寸。

## 文件

- `configs/rmul_2027.json`：源文件位置、坐标换算、手册标称尺寸。
- `scripts/build_scene.py`：读取二进制 STL，核对指定区域尺寸，导出 USD；没有凸包化、简化或填洞。
- `scenes/aurora_terrain.usda`：完整场地、灯光、总览/隧道/高地/俯视相机；打开此文件不再依赖原 STL。
- `outputs/dimension_audit.json`：可复查的尺寸核对报告与源 STL SHA-256。
- `outputs/aurora_preview.png`：运行截图命令后生成的总览和局部视图拼图。

材质分区仅用于显示，没有添加图纸外的几何。STL 的场地标记细节原样保留。
网格启用静态三角面碰撞，`approximation=none`，避免把整场地凸包化后封住隧道。
场景显示材质不是训练语义；入口位置与可见性标注由采集器另行生成，保存在数据集 JSON 中。

## 坐标与单位

STL 不自带可靠单位信息。通过手册多项尺寸核对，源数值按毫米解释，源 −Y 方向朝上。
原始外包围盒为 12600 × 520 × 8600（源 X/Y/Z），包含外围结构；场内净尺寸是 12000 × 8000。
导出场景用米、Z 轴朝上，场地中心地面为原点：

```text
X = (source_x - 6300) / 1000
Y = (source_z - 4300) / 1000
Z = (420 - source_y) / 1000
```

这是保持右手系的旋转、平移和统一尺度换算，不反射、不改变三角面绕序。

## 使用已有虚拟环境

本机环境为 `/home/lsy/miniconda3/envs/isaaclab`，Isaac Sim 6.0.1。

```bash
conda activate isaaclab
python scripts/build_scene.py
python scripts/preview_scene.py --gui
```

打开窗口并保存预览图：

```bash
python scripts/preview_scene.py --gui --capture
```

仅渲染截图：`python scripts/preview_scene.py`。
在 Isaac Sim 中也可以直接打开 USD，选择 `/World/Cameras/Overview`、`Tunnel`、`Stairs` 或 `Top`。
`Stairs` 相机名为兼容早期预览脚本保留，实际显示的是高地。
首次渲染可能需要编译着色器。渲染需要可访问的 NVIDIA GPU，场景生成和尺寸核对不需要 GPU。

导入器的尺寸审计区域针对这份特定 STL 的源坐标定义；换用其他模型时需要重新确认坐标与审计区域。

## 数据与手动训练

详细流程见 `docs/TRAINING.md`，数据定义见 `docs/DATASET.md`。

```bash
conda activate isaaclab
python scripts/validate_dataset.py --dataset datasets/tunnel_v1
python scripts/train.py --config configs/train_tunnel.json --device cuda
```

最后一条才会真正开始训练。`--dry-run` 只做数据加载、前向和损失计算，不创建优化器、不更新参数、不保存权重。
只读监控：`python scripts/monitor.py --run runs/aurora_tunnel_v1 --watch`。

## 独立 Gazebo 验证

不启动定位与导航，仅启动 Gazebo、机器人、Aurora 推理和 RViz：

```bash
source /opt/ros/humble/setup.bash
source /home/lsy/cs_project/ray-sentry-ying-/install/setup.bash
ros2 launch /home/lsy/cs_project/aurora/launch/aurora_gazebo.launch.py
```

机器人、点云和隧道入口预测在同一 RViz 中显示；记录保存在 `runs/gazebo_时间戳/`。
不要与其他仿真重复启动。输入方向校正、记录格式及验证限制见 `docs/SIM_VALIDATION.md`。
