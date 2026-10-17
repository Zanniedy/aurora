#pragma once
#include "home_mode.hpp"
#include "auto_sentry/brain/rmuc_2026/dog_mode.hpp"
#include "auto_sentry/brain/rmuc_2026/mode_base.hpp"
#include "utils/drivers/serial_driver.hpp"
#include "utils/utils.hpp"
#include <memory>
#include <string>

//模型判断 用来决定启动哪个模型
namespace aurora::sentry_brain {
inline std::unique_ptr<ModeBase> create_brain_mode(
    rcl::RclcppNode& rcl_node,
    rcl::TF& rcl_tf,
    const YAML::Node& config,
    std::shared_ptr<SerialDriver> serial
) {
    if (!config["enable"].as<bool>()) {
        return nullptr;
    }
    auto mode_str = utils::to_upper(config["mode"].as<std::string>());
    if (mode_str == "HOME") {
        return std::make_unique<HomeMode>(rcl_node, rcl_tf, config["home"], serial);
    } else if (mode_str == "DOG") {
        return std::make_unique<DogMode>(rcl_node, rcl_tf, config["dog"], serial);
    }
    // Add more modes as needed
    throw std::invalid_argument("Unknown mode: " + mode_str);
}
} // namespace aurora::sentry_brain