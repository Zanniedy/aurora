#pragma once
#include "auto_sentry/radar/type.hpp"
#include "utils/impl.hpp"
#include <Eigen/src/Core/Matrix.h>
#include <utility>
#include <vector>
#include <yaml-cpp/node/node.h>
namespace aurora::radar_detect {
class LidarLocation {
public:
    LidarLocation(const YAML::Node& node);
    // CarPool detect(const std::vector<Eigen::Vector3f>& pts);
    std::pair<Eigen::Vector3f, Eigen::Vector3f> get_target_map_bbox();
    std::vector<Eigen::Vector3f>& get_target_map_pts();
    AURORA_IMPL_DEFINITION(LidarLocation)
};
} // namespace aurora::radar_detect