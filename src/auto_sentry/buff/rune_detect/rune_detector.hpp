#pragma once
#include "auto_sentry/buff/type.hpp"
#include "auto_sentry/base/common.hpp"
#include "utils/impl.hpp"
#include <opencv2/core/types.hpp>
#include <yaml-cpp/node/node.h>
namespace aurora::auto_buff {
class RuneDetector {
public:
    RuneDetector(const YAML::Node& config);
    RuneDetection detect(const CommonFrame& frame, const cv::Rect& focus, EnemyColor enemy_color);
    AURORA_IMPL_DEFINITION(RuneDetector)
};
} // namespace aurora::auto_buff