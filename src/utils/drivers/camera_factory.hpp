#pragma once

#include "utils/drivers/camera.hpp"
#include <memory>
#include <string>
#include <yaml-cpp/node/node.h>

namespace aurora {


    //自瞄系统下的 相机的相关的类的定义
std::unique_ptr<Camera> create_camera(
    const YAML::Node& config,
    Scheduler& scheduler,
    const std::string& default_type = "hik"
);

std::unique_ptr<Camera>
create_camera(const YAML::Node& config, const std::string& default_type = "uvc");

} // namespace aurora
