# aurora logger

基于 spdlog 的静态日志库：彩色控制台 + 按时间戳滚动的文件日志。目录超过阈值时会清理旧日志。

## 构建

```bash
cmake -S . -B build
cmake --build build -j
ctest --test-dir build --output-on-failure
```

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
