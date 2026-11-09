# Aurora：由用户手动启动训练

## 已实现的训练模式

监督学习、单类别、多入口位置检测，不是强化学习，也不是逐点分割。
网络名为 `Aurora`。输入是单帧点云，不使用传感器世界位姿、标注 ID 或其他真值特征。

```text
xyz 点云
→ 5 cm 体素统计
→ 按高度层排列的 BEV 特征 [36, 200, 200]
→ 三尺度二维卷积与特征融合
→ 入口热力图 [1, 100, 100] + XY 单元偏移与 Z 高度 [3, 100, 100]
→ 局部极大值筛选 → 入口位置 + 置信度
```

当前是“高度分层体素特征 + 2D CNN”的轻量基线，**不是已经实现的稀疏 3D 卷积骨干**。
水平输入范围为雷达周围 ±5 m，垂直范围为 -0.8 至 1.0 m。
热力图输出步长为 0.1 m，XY 偏移回归提供单元内位置；这不等于承诺 0.1 m 或更高的实际定位精度。
训练损失为高斯关键点热力图 focal loss 与 Smooth L1 位置回归。

训练增强对点云和位置标签同时做绕 Z 轴旋转，另加少量点噪声和丢点；不缩放隧道尺寸。
第一版仅使用 XYZ，不依赖仿真中不存在的可靠反射率。

## 环境和预检查

使用已有 `isaaclab` 环境，无需安装新的 CUDA/PyTorch：

```bash
cd /home/lsy/cs_project/aurora
conda activate isaaclab
python scripts/validate_dataset.py --dataset datasets/tunnel_v1
python scripts/train.py --config configs/train_tunnel.json --device cpu --workers 0 --batch-size 2 --dry-run
```

`--dry-run` **没有优化器、没有反向传播、没有参数更新、没有权重保存**。
它不是训练，也不能用输出的随机初始化损失衡量模型效果。
显存紧张时，先手动关闭不用的 Isaac Sim 预览窗口。

## 真正开始训练：这一条由用户执行

```bash
python -u scripts/train.py --config configs/train_tunnel.json --device cuda
```

默认 80 epochs、batch size 8、AdamW、余弦学习率调度；这些是基线参数，不是已调优结果。
支持 CUDA 混合精度，支持时优先 BF16，否则使用 FP16 与 GradScaler。
修改 epoch 或 batch size 可以用 `--epochs 40 --batch-size 4`，新的实验应另指定 `--run runs/实验名`。
不带 `--resume` 时不会覆盖已有实验目录。

## 日志和监督

```text
runs/aurora_tunnel_v1/
  config.json
  state.json
  metrics.jsonl
  last.pt
  best.pt
  tensorboard/
```

- `state.json`：阶段、进度、心跳、最近 loss、CUDA 已分配显存和异常信息。
- `metrics.jsonl`：每 epoch 的训练损失、验证 precision/recall/F1、定位误差及负帧误报率。
- `last.pt`：最近完整 epoch 的模型、优化器、调度器等状态。
- `best.pt`：按验证 F1 选取；F1 相同时优先匹配目标的较小平均定位误差。

只读监控，不启动或修改训练：

```bash
python scripts/monitor.py --run runs/aurora_tunnel_v1 --watch
```

TensorBoard：

```bash
tensorboard --logdir runs/aurora_tunnel_v1/tensorboard --host 127.0.0.1
```

监控器提示连续零召回、可能的过拟合和心跳停滞，不自动改参数或重启训练。
启动后在当前对话告知实验目录，助手即可读取这些文件检查进展；不意味着关闭对话后仍有人在后台值守。

## 评估定义

采用按置信度排序的一对一三维距离匹配，默认匹配阈值 0.20 m，检测置信度阈值 0.25。
同时记录漏检和误报；平均误差/P95 仅对正确匹配的目标统计，没有匹配时为 `null`，不是 0。
这里报告的是固定阈值位置检测指标，**不是 3D 框 IoU mAP**。

训练期间只评估 `val`，不依据测试集选权重。
置信度阈值应在验证集选择，确定方案后再做一次测试集评估：

```bash
python scripts/evaluate.py --checkpoint runs/aurora_tunnel_v1/best.pt --split test --device cuda
```

这是近似仿真数据上的结果；真实泛化仍需独立真实点云测试。

## 续训和真实数据微调

同一实验从最近完整 epoch 续训：

```bash
python scripts/train.py --config configs/train_tunnel.json --resume runs/aurora_tunnel_v1/last.pt --device cuda
```

若第一轮尚未完成就中断，可能还没有 checkpoint。不会假称保存了未完成 batch 的进度。
续训保持原配置和总 epoch 计划；数据清单指纹不同或关键超参数改变会被拒绝。
数据指纹覆盖 metadata 和 split 清单；完整点云/标签内容摘要另外保存在数据校验报告中。

真实数据微调需先使用相同 schema 准备真实标注和独立划分，另建训练配置，降低学习率，并使用新实验目录：

```bash
python scripts/train.py --config configs/real_finetune.json --finetune runs/aurora_tunnel_v1/best.pt --device cuda
```

`configs/real_finetune.json` 目前尚不存在，待真实数据准备好后再创建；这不是当前可以直接执行的命令。
`--finetune` 只载入模型权重，不继承旧优化器。

## 单帧推理

训练完成后：

```bash
python scripts/infer.py --checkpoint runs/aurora_tunnel_v1/best.pt \
  --points datasets/tunnel_v1/sim/sequence_0000/points/000000.npz --device cuda
```

输出为雷达坐标系下的入口底边中点、类别和置信度。进入真实机器人前还要核对实际雷达坐标约定和安装外参。
