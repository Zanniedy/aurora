cmake_minimum_required(VERSION 3.14)

# 必须在 project() 之前打开，CMake Tools 和 clangd 都读这份数据库。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# C 只给 src/party/others/liblzf 用。
project(aurora VERSION 0.1.0 LANGUAGES C CXX)

# 自瞄、哨兵和导航代码统一使用 C++23。
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS
        Debug Release RelWithDebInfo MinSizeRel)
endif()

# 单体 CMake。ROS 2 只作为普通库引入，不用 ament / colcon 组织工程。
# 只把前缀放进搜索路径。不要在 logger 之前 find_package(rclcpp)：
# Humble 会定义 spdlog::spdlog，指向发行版 1.9，logger 就会跳过 spdlog 1.15。
if(DEFINED ENV{AMENT_PREFIX_PATH})
    string(REPLACE ":" ";" _aurora_ros_prefixes "$ENV{AMENT_PREFIX_PATH}")
    list(PREPEND CMAKE_PREFIX_PATH ${_aurora_ros_prefixes})
elseif(DEFINED ENV{ROS_DISTRO} AND EXISTS "/opt/ros/$ENV{ROS_DISTRO}")
    list(PREPEND CMAKE_PREFIX_PATH "/opt/ros/$ENV{ROS_DISTRO}")
endif()

# conda 里的 yaml-cpp/fmt 会把 conda 的 libcurl 带进链接，和系统 libgdal 冲突。
# make.sh 会先 deactivate；这里再兜底，避免在 conda 终端里直接 cmake 时串进来。
if(DEFINED ENV{CONDA_PREFIX})
    list(APPEND CMAKE_IGNORE_PREFIX_PATH "$ENV{CONDA_PREFIX}")
endif()
if(EXISTS "$ENV{HOME}/miniconda3")
    list(APPEND CMAKE_IGNORE_PREFIX_PATH "$ENV{HOME}/miniconda3")
endif()

find_library(AURORA_SYSTEM_CURL NAMES curl
    PATHS /usr/lib/x86_64-linux-gnu /usr/lib64 /usr/lib
    NO_DEFAULT_PATH)

# logger 自带 CMakeLists，直接作为子工程。同进程里的目标链接 aurora::aurora_logger。
add_subdirectory(src/party/mine/logger)
add_subdirectory(src/mapper)

option(AURORA_BUILD_RADAR "Build radar station (needs Open3D)" OFF)
option(AURORA_WITH_TRT "Build TensorRT detector (radar_detect needs it)" OFF)
option(AURORA_WITH_OPENVINO "Build OpenVINO auto-aim detector backend" OFF)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)
set(AURORA_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(AURORA_GENERATED_DIR ${CMAKE_BINARY_DIR}/generated)
set(AURORA_BIN_DIR ${CMAKE_BINARY_DIR}/bin)

# ROOT_DIR：配置文件里的 ${ROOT_DIR} 和保存 pcd 等路径都相对工程根目录。
set(AURORA_ROOT_DIR ${CMAKE_CURRENT_SOURCE_DIR})
configure_file(src/param_deliver.h.in ${AURORA_GENERATED_DIR}/param_deliver.h @ONLY)

if(AURORA_WITH_TRT)
    find_package(CUDAToolkit REQUIRED)
    find_package(TensorRT REQUIRED)
    enable_language(CUDA)
    set(CMAKE_CUDA_STANDARD 17)
    add_library(aurora_trt INTERFACE)
    target_compile_definitions(aurora_trt INTERFACE USE_TRT)
    target_include_directories(aurora_trt INTERFACE ${TensorRT_INCLUDE_DIR})
    target_link_libraries(aurora_trt INTERFACE
        TensorRT::TensorRT TensorRT::nvonnxparser CUDA::cudart CUDA::nppicc)
endif()

if(AURORA_WITH_OPENVINO)
    find_package(OpenVINO REQUIRED COMPONENTS Runtime ONNX)
endif()

add_subdirectory(src/party/others)
add_subdirectory(src/utils)
add_subdirectory(src/rcl)
add_subdirectory(src/auto_sentry)
add_subdirectory(src/navigation)
add_subdirectory(src/runtime)

# clangd helper: 唯一的 .cpp，使所有 INTERFACE 依赖的 include 路径
# 出现在 compile_commands.json 里，消除虚假报错。不参与正式构建目标。
add_library(aurora_clangd_helper OBJECT EXCLUDE_FROM_ALL
    src/clangd_dummy.cpp
)
target_link_libraries(aurora_clangd_helper PRIVATE
    aurora_auto_sentry
    aurora_slam
)
target_include_directories(aurora_clangd_helper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/auto_sentry
    ${CMAKE_CURRENT_SOURCE_DIR}/src/mapper/src
)
