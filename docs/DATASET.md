# 隧道数据 v1

## 真实性边界

几何来自用户提供的 STL，经过手册尺寸核对后导出的同一 `scenes/aurora_terrain.usda`。
采集器读取实际三角网格，使用 NVIDIA Warp 的最近交点射线查询，保留高地、围墙等对射线的遮挡。
**这不是 Isaac Sim RTX LiDAR 的输出，也不是经过校准的 MID360 仿真。**

本批配置水平 360°、垂直 -7° 至 +52°，每帧 100 ms、20000 条候选射线。
射线方位角和仰角独立均匀随机，**不复现 Livox 非重复扫描的时间相关轨迹和角密度**。
只保存击中实体且通过量程/丢点筛选的回波，因此每帧点数不是固定 20000。
量程噪声和丢点比例是可配置的增强假设，不是测得的 MID360 标定结果。
不模拟反射率、多回波、多径、逐点运动畸变、机器人本体遮挡或不同材质的激光响应。

用途是先把位置标注、体素输入、损失、训练监控和推理接口跑通。
不能凭这一批数据的验证分数声称模型已具备真实 MID360 部署性能。

## 文件布局

```text
datasets/tunnel_v1/
  dataset.json
  validation_report.json
  preview.png
  splits/{train,val,test}.txt
  sim/sequence_0000/
    sequence.json
    points/000000.npz
    labels/000000.json
```

NPZ 只包含 `xyz: float32[N,3]` 和与回波一一对应的 `time_offset: float32[N]`。
坐标是该帧雷达坐标系，单位米；逐点时间单位秒，从帧起点算起。
没有伪造反射率字段。JSON 中的世界位姿不输入网络，仅供标注和审计。

标签包括：
- `objects`：有效 `tunnel` 入口，位置是入口底边中点。
- `ignored`：观测不足或歧义入口，在训练热力图中屏蔽其邻域；评估时附近预测不算误报。
- `instance_id` 和 `entrance_id`：区分两个物理隧道及各自两端入口，不增加检测类别。
- `T_world_lidar`：把列向量雷达坐标变换到世界坐标的 4×4 矩阵。
- `visible_probe_fraction`、`support_points`：保留自动可见性规则的审计信息。

无有效目标的帧使用 `objects: []`，可能仍含 `ignored`，与“所有位置都是确定背景”不同。
入口的观测要求是朝向传感器、在标注距离内、开口探测射线有足够视场内直视比例，并且周边有结构回波。
完全不可观测或背向入口不作为正样本。标签不是点级语义分割，也不把金属板包围盒误当成入口。

## 分组与采样

默认 96 组，每组 16 帧；组内是邻近静态视点，不是带运动畸变的完整轨迹。
按组划分训练/验证/测试，按负样本和正样本组的主要入口分层，避免验证集只覆盖某一侧入口；禁止跨 split 共享 sequence。
采集参数中的随机种子和每组种子都落盘；不同计算后端可能有浮点交点差异，不承诺逐比特一致。

基础安装高度 0.15–0.30 m，组内另有 ±15 mm 高度扰动；俯仰 ±6° 等是初始采样假设。拿到实际安装位姿后应重新对齐。
隧道净高保持 250 mm，未使用改变结构尺度的增强。
当前只有一个固定场地布局；即使没有跨组泄漏，验证集仍然只是同布局的留出视点，不能替代真实场景测试。

## 重新采集

```bash
conda activate isaaclab
python scripts/collect_dataset.py --device cuda:0 --output datasets/tunnel_v2
python scripts/validate_dataset.py --dataset datasets/tunnel_v2
```

CPU 也可采集：`--device cpu`。所有输出必须写入新目录，不覆盖旧数据。
生成过程中 `dataset.json.status` 为 `collecting`，完整结束后才变为 `complete`；训练器拒绝未完成数据。
若采样中断，保留原目录以供排查，用新目录重新采集；当前不支持断点续采。
`datasets/tunnel_v1_incomplete_attempt1` 是第一次采样重试不足留下的未完成批次，**不要用于训练**。

校验器检查数据类型、有限数值、逐点时间、刚体变换、入口世界坐标往返、可见性阈值、组泄漏及跨 split 重复点云。
这些检查不能证明可见性标注百分之百正确，所以还应查看 `preview.png`，并继续抽查边界视角。
