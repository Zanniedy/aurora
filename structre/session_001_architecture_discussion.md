# Session 001 — 架构讨论：无人哨兵项目 Aurora

**日期：** 2026-09-27  
**参与者：** lsy（RM哨兵负责人）

---

## 项目背景

- **项目名称：** aurora（新建个人哨兵项目）
- **角色：** lsy 负责本赛季RM无人哨兵全套，包括导航 + 自瞄的设计
- **目标：** 从两套现有代码出发，形成自己风格和架构的新项目

---

## 现有代码库

### 自瞄：`awakening-latest`
- 路径：`/home/lsy/cs_project/awakening-latest`
- 构建：非标准 ROS2 package，单体 CMake 项目，有自己的 `_rcl` 封装层
- 命名空间：`awakening::`
- 核心目录：
  - `src/tasks/auto_aim/` — 自瞄任务
  - `src/tasks/sentry_brain/rmuc_2026/` — 哨兵决策逻辑
  - `src/runtime/sentry.cpp` — 哨兵运行时入口
  - `src/utils/` — 驱动（相机、串口）、CUDA、调度器等
  - `src/_rcl/` — 自封装的 ROS2 node/tf 层

### 导航：`rose_navigation`
- 路径：`/home/lsy/cs_project/nav/cs/src/rose_navigation`
- 构建：标准 ROS2 package（ament_cmake）
- 目录划分极清晰：
  - `src/lm/` — Lidar-IMU 定位（Small-PointLIO，ESKF）
  - `src/map/` — 占用地图 + ESDF
  - `src/planner/` — A* 路径搜索 + MINCO 轨迹优化 + LMPC 控制

---

## 架构关键结论

### 底盘 / 云台分离
- 导航控制底盘，自瞄控制云台，**两者松耦合**
- 唯一共享资源：**一个串口**（与下位机通信）
- ROS2 仅作通信工具使用，不是框架约束

### 哨兵决策逻辑位置
- `awakening-latest/src/tasks/sentry_brain/rmuc_2026/home_mode.hpp`
- 决策采用优先级链：低血量 → 低弹量 → 打前哨 → 护前哨 → 防御要塞 → 巡逻
- 导航目标点由 sentry_brain 产生，推给导航侧执行

### 导航 ↔ 自瞄 的信息流
- **当前：** 串口是唯一的物理耦合点，两侧独立运行
- **目标：** 二者最终应支持紧耦合
  - 自瞄可读取导航速度做前馈补偿（底盘运动补偿）
  - 导航可读取自瞄目标信息影响路径规划（如：追着目标移动、规避遮挡）
- 架构设计需为此预留接口，不能做成死的

---

## 调度器讨论

### 现有实现（awakening Scheduler）
- 有向数据流图，Source/Task/IOPair 抽象，TBB `task_group` 执行下游节点
- **已知瓶颈：** `queue_mutex_` 是全局串行点，`process_queue` 每次只取一个节点，TBB 工作窃取优势被抵消

### 候选方向
- **TBB `flow_graph`（首选）：** 现有 node 抽象与 flow_graph 高度同构，调度/背压/路由由 TBB 内核处理，`join_node` 原生支持多输入同步，未来自瞄+导航紧耦合时直接受益
- **无锁队列（最小改动）：** `task_queue_` 换 `tbb::concurrent_queue`，消掉全局锁
- **C++23 coroutine（远期）：** 暂不考虑

## 构建风格（已定）

**结论：单体 CMake，rclcpp 等 ROS2 组件作为普通库 find_package 引入。**

理由：
- ament workspace 对 aurora 唯一有价值的是调试期 rviz2，但普通 rclcpp 就够发 topic，不需要整套 ament 体系
- 哨兵单机单进程部署，没有多机自动发现需求
- **"跑打"场景**：MPPI/MPC 预测未来轨迹 → 喂给自瞄做前馈补偿。这个数据流必须在同进程内完成，跨进程 topic 的延迟和抖动不可控

**连带结论：sentry_brain 放 aurora 主进程**，需要同时拿导航轨迹和自瞄目标状态做决策，跨进程协调代价太高。

## 待讨论（未定）

- [x] 构建风格 → 单体 CMake
- [x] sentry_brain 归属 → aurora 主进程
- [ ] 串口共享的具体实现方式
- [ ] 调度器：是否迁移到 TBB flow_graph
- [ ] 代码风格偏好（命名、注释、模块边界）
