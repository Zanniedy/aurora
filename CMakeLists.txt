cmake_minimum_required(VERSION 3.14)

# 必须在 project() 之前打开，CMake Tools 和 clangd 都读这份数据库。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

project(aurora VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
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

# logger 自带 CMakeLists，直接作为子工程。同进程里的目标链接 aurora::aurora_logger。
add_subdirectory(party/mine/logger)
add_subdirectory(mapper)
