# Aurora

Aurora 是迁移后的单体 CMake 工程，包含哨兵自瞄、能量机关、雷达站、导航和相关工具。

## 快速开始

```bash
source /opt/ros/humble/setup.bash
./run.sh build
./run.sh run auto_aim_probe config/sentry.yaml
```

默认构建关闭 OpenVINO、TensorRT 和雷达。要运行真实自瞄，请按配置打开 `AURORA_WITH_OPENVINO`；要构建雷达站，请同时打开 `AURORA_BUILD_RADAR` 和 `AURORA_WITH_TRT`。

完整的模块说明、模型清单、启动命令、配置修改、模型替换、导航地图迁移和故障排查见：

- [Aurora 开发与二次开发文档](docs/aurora_development.md)
