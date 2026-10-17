#pragma once
#include "auto_sentry/base/common.hpp"
#include "auto_sentry/radar/type.hpp"
#include "type.hpp"
#include "utils/impl.hpp"
#include <opencv2/core/types.hpp>
#include <vector>
#include <yaml-cpp/node/node.h>
namespace aurora::radar_detect {
class Detector {
public:
    Detector(const YAML::Node& config);
    std::vector<Car> detect(const CommonFrame& frame, const cv::Rect& focus);
    std::vector<Armor> detect_armors(const CommonFrame& frame, const cv::Rect& focus);
    AURORA_IMPL_DEFINITION(Detector)
};
} // namespace aurora::radar_detect