# aurora logger

基于 spdlog 的静态日志库：彩色控制台 + 按时间戳滚动的文件日志。目录超过阈值时会清理旧日志。

## 构建

```bash
./make.sh
ctest --test-dir build --output-on-failure
```

`./make.sh` 同时会：

- 找到本机、`CMAKE_PREFIX_PATH`、`--prefix` 和 `third_party/` 里的库
- 编译根目录的纯 CMake 工程；以后放进子目录的 ROS 2 包也会一起编
- 把所有 `compile_commands.json` 合并到项目根目录，给 clangd 用

改完后在编辑器里执行 `clangd: Restart language server`。

## 使用

```cpp
#include "log.hpp"

int main() {
    aurora::init_logger();                 // 默认写到 ~/.aurora/log
    // aurora::init_logger("log");          // 或指定目录
    AURORA_INFO("hello {}", "aurora");
    aurora::logger::shutdown();
}
```
