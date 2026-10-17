#pragma once
#include "auto_sentry/buff/rune_track/rune_target.hpp"
#include "auto_sentry/buff/type.hpp"
#include "auto_sentry/base/common.hpp"
#include "utils/impl.hpp"
#include <yaml-cpp/node/node.h>
namespace aurora::auto_buff {
class RuneTracker {
public:
    RuneTracker(const YAML::Node& config);
    AURORA_IMPL_DEFINITION(RuneTracker)
    RuneTarget track(
        RuneDetection& detection,
        const CameraInfo& camera_info,
        const ISO3& camera_cv_in_odom,
        int frame_id
    );
    int get_count();
    void reset_count();
};
} // namespace aurora::auto_buff