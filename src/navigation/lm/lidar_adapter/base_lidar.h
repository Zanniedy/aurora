/**
 * This file is part of Small Point-LIO, an advanced Point-LIO algorithm
 * implementation. Copyright (C) 2025  Yingjie Huang Licensed under the MIT
 * License. See License.txt in the project root for license information.
 */

#pragma once

#include "navigation/lm/common.hpp"
#include <rclcpp/node.hpp>

namespace aurora::nav::lm {

class LidarAdapterBase {
public:
    virtual ~LidarAdapterBase() = default;
    virtual void setup_subscription(
        rclcpp::Node* node,
        const std::string& topic,
        std::function<void(std::vector<common::Point>&, const rclcpp::Time&)> callback
    ) = 0;
};

} // namespace aurora::nav::lm
