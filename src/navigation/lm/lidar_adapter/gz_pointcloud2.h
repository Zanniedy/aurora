/**
 * Gazebo-bridged PointCloud2 adapter.
 * ros_gz_bridge outputs standard PointCloud2 with only x/y/z fields,
 * no Livox-specific "tag" or "timestamp" fields.
 * Timestamp is taken from the message header.
 */

#pragma once

#include "base_lidar.h"
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>

namespace aurora::nav::lm {

class GzPointCloud2Adapter : public LidarAdapterBase {
private:
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr subscription;

public:
    inline void setup_subscription(
        rclcpp::Node* node,
        const std::string& topic,
        std::function<void(std::vector<common::Point>&, const rclcpp::Time&)> callback
    ) override {
        subscription = node->create_subscription<sensor_msgs::msg::PointCloud2>(
            topic,
            rclcpp::SensorDataQoS(),
            [callback](const sensor_msgs::msg::PointCloud2& msg) {
                double base_time =
                    msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9;

                sensor_msgs::PointCloud2ConstIterator<float> iter_x(msg, "x");
                sensor_msgs::PointCloud2ConstIterator<float> iter_y(msg, "y");
                sensor_msgs::PointCloud2ConstIterator<float> iter_z(msg, "z");

                size_t size = msg.width * msg.height;
                std::vector<common::Point> pointcloud;
                pointcloud.reserve(size);

                for (size_t i = 0; i < size; ++i) {
                    common::Point p;
                    p.position << *iter_x, *iter_y, *iter_z;
                    p.timestamp = base_time;
                    pointcloud.push_back(p);
                    ++iter_x;
                    ++iter_y;
                    ++iter_z;
                }

                callback(pointcloud, msg.header.stamp);
            }
        );
    }
};

} // namespace aurora::nav::lm
