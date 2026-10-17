# rclcpp 薄封装（节点、tf），当前以头文件形式提供。
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

add_library(aurora_rcl INTERFACE)
add_library(aurora::rcl ALIAS aurora_rcl)
target_link_libraries(aurora_rcl INTERFACE
    aurora::utils
    rclcpp::rclcpp
    geometry_msgs::geometry_msgs__rosidl_typesupport_cpp
    nav_msgs::nav_msgs__rosidl_typesupport_cpp
    sensor_msgs::sensor_msgs__rosidl_typesupport_cpp
    visualization_msgs::visualization_msgs__rosidl_typesupport_cpp
    tf2_ros::tf2_ros
    tf2_geometry_msgs::tf2_geometry_msgs
)
