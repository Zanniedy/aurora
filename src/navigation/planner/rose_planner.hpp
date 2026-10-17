#pragma once

#include <rclcpp/node.hpp>
namespace aurora::nav::planner {
class RosePlanner {
public:
    RosePlanner(rclcpp::Node& node);
    ~RosePlanner();
    struct Impl;
    std::unique_ptr<Impl> _impl;
};
} // namespace aurora::nav::planner