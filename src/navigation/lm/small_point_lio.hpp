#pragma once
#include <rclcpp/node.hpp>
namespace aurora::nav::lm {
class SmallPointLIO {
public:
    SmallPointLIO(rclcpp::Node& node);
    ~SmallPointLIO();
    struct Impl;
    std::unique_ptr<Impl> _impl;
};
} // namespace aurora::nav::lm