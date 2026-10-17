#pragma once
#include "auto_sentry/aim/armor_track/armor_target.hpp"
#include "auto_sentry/aim/type.hpp"
#include "auto_sentry/base/common.hpp"
#include "utils/impl.hpp"
#include <yaml-cpp/node/node.h>
namespace aurora::auto_aim {
class ArmorTracker {
public:
    ArmorTracker(const YAML::Node& config);
    [[nodiscard]] ArmorTarget track(
        Armors& armors,
        const CameraInfo& camera_info,
        const ISO3& camera_cv_in_odom,
        int frame_id
    );
    int get_count();
    void reset_count();
    void set_sentry(bool is_sentry);
    AURORA_IMPL_DEFINITION(ArmorTracker)
};
} // namespace aurora::auto_aim