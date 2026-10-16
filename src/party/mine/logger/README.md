# aurora logger

基于 spdlog 的静态日志库：彩色控制台 + 按时间戳滚动的文件日志。目录超过阈值时会清理旧日志。

## 构建

```bash
./make.sh
ctest --test-dir build --output-on-failure
```

`./make.sh` 会把静态库装到 `install/`。同一次构建里的 ROS 2 包可以直接 `find_package(aurora_logger)`。

## 同一个 CMake 工程

```cmake
target_link_libraries(your_target PRIVATE aurora::aurora_logger)
```

## 别的 CMake / ROS 2 工程

```cmake
find_package(aurora_logger REQUIRED)
target_link_libraries(your_target PRIVATE aurora::aurora_logger)
```

```bash
cmake -S . -B build -DCMAKE_PREFIX_PATH=/path/to/logger/install
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
