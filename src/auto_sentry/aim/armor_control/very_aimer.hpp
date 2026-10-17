#pragma once
#include "auto_sentry/aim/armor_track/armor_target.hpp"
#include "auto_sentry/aim/auto_aim_fsm.hpp"
#include "auto_sentry/base/common.hpp"
#include "utils/impl.hpp"
#include <memory>
#include <yaml-cpp/node/node.h>

namespace aurora::auto_aim {
class VeryAimer {
public:
    VeryAimer(const YAML::Node& config);
    AURORA_IMPL_DEFINITION(VeryAimer)
    [[nodiscard]] GimbalCmd very_aim(
        const ArmorTarget& target,
        double bullet_speed,
        const AutoAimFsm& fsm,
        const ISO3& shoot_in_gimbal_odom,
        const ISO3& gimbal_in_gimbal_odom
    );
    std::pair<double, double> get_yaw_pitch_offset();
    void set_operator_offset(std::pair<double, double> offset);
};
} // namespace aurora::auto_aim