# 建图工具，角色上类比 slam_toolbox：雷达/地图/位姿，而不是导航规划。
# 作为 aurora 的子目录使用。单独打开本目录时再成自己的工程。
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    cmake_minimum_required(VERSION 3.14)
    set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
    project(aurora_slam VERSION 0.1.0 LANGUAGES CXX)
    set(CMAKE_CXX_STANDARD 17)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_CXX_EXTENSIONS OFF)
    if(DEFINED ENV{AMENT_PREFIX_PATH})
        string(REPLACE ":" ";" _aurora_ros_prefixes "$ENV{AMENT_PREFIX_PATH}")
        list(PREPEND CMAKE_PREFIX_PATH ${_aurora_ros_prefixes})
    elseif(DEFINED ENV{ROS_DISTRO} AND EXISTS "/opt/ros/$ENV{ROS_DISTRO}")
        list(PREPEND CMAKE_PREFIX_PATH "/opt/ros/$ENV{ROS_DISTRO}")
    endif()
endif()

if(NOT TARGET aurora::aurora_logger)
    find_package(aurora_logger REQUIRED)
endif()

find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS filesystem system)
# 不用 pcl_visualization。系统 VTK 的链接接口带 MPI::MPI_C，本工程没有 C 语言。
set(CMAKE_DISABLE_FIND_PACKAGE_VTK TRUE)
find_package(PCL REQUIRED COMPONENTS common io filters kdtree search registration)
find_package(OpenCV REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(TBB REQUIRED)
find_package(Ceres REQUIRED)
find_package(OpenMP REQUIRED)

find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(message_filters REQUIRED)
find_package(std_srvs REQUIRED)

# pcl_conversions 是纯头文件，Humble 没有导出目标。
if(NOT TARGET pcl_conversions::pcl_conversions)
    add_library(pcl_conversions::pcl_conversions INTERFACE IMPORTED)
    set_target_properties(pcl_conversions::pcl_conversions PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${pcl_conversions_INCLUDE_DIRS}"
    )
endif()

# 现在只有头文件。有 .cpp 之后改成 STATIC，并把源文件加到下面。
add_library(aurora_slam INTERFACE)
add_library(aurora::slam ALIAS aurora_slam)

target_include_directories(aurora_slam INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
)

target_link_libraries(aurora_slam INTERFACE
    aurora::aurora_logger
    Eigen3::Eigen
    pcl_common
    pcl_io
    pcl_filters
    pcl_kdtree
    pcl_search
    pcl_registration
    ${OpenCV_LIBS}
    yaml-cpp
    TBB::tbb
    Ceres::ceres
    Boost::filesystem
    Boost::system
    OpenMP::OpenMP_CXX
    rclcpp::rclcpp
    sensor_msgs::sensor_msgs__rosidl_typesupport_cpp
    nav_msgs::nav_msgs__rosidl_typesupport_cpp
    geometry_msgs::geometry_msgs__rosidl_typesupport_cpp
    visualization_msgs::visualization_msgs__rosidl_typesupport_cpp
    tf2_ros::tf2_ros
    tf2_eigen::tf2_eigen
    tf2_geometry_msgs::tf2_geometry_msgs
    pcl_conversions::pcl_conversions
    message_filters::message_filters
    std_srvs::std_srvs__rosidl_typesupport_cpp
)
