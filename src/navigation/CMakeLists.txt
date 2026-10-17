# 导航：lm（Small-PointLIO 定位）/ map（占用地图 + ESDF）/ planner（A* + MINCO + LMPC）。
# 迁移自 rose_navigation，原来的三个 rclcpp_components 节点改成 runtime/nav_*.cpp 三个进程。
find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(TBB REQUIRED)
find_package(osqp REQUIRED)
find_package(OsqpEigen REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

file(GLOB_RECURSE AURORA_NAV_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp)
add_library(aurora_nav STATIC ${AURORA_NAV_SOURCES})
add_library(aurora::nav ALIAS aurora_nav)

target_include_directories(aurora_nav PUBLIC
    ${AURORA_SRC_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${AURORA_GENERATED_DIR}
)
# 原工程的优化选项，ESKF 和轨迹优化对这几项比较敏感。
target_compile_options(aurora_nav PUBLIC -march=native -ffast-math -fno-math-errno)
target_link_libraries(aurora_nav PUBLIC
    aurora::party_others
    aurora_pcd_io
    Eigen3::Eigen
    ${OpenCV_LIBS}
    yaml-cpp
    TBB::tbb
    osqp::osqp
    OsqpEigen::OsqpEigen
    rclcpp::rclcpp
    sensor_msgs::sensor_msgs__rosidl_typesupport_cpp
    geometry_msgs::geometry_msgs__rosidl_typesupport_cpp
    nav_msgs::nav_msgs__rosidl_typesupport_cpp
    std_srvs::std_srvs__rosidl_typesupport_cpp
    visualization_msgs::visualization_msgs__rosidl_typesupport_cpp
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
    ${AURORA_SYSTEM_CURL}
)
