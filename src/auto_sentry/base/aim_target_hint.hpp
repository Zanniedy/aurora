#pragma once
// 自瞄 -> 决策/导航 的目标接口。决策层只依赖这个结构，不依赖自瞄内部的 ArmorTarget，
// 自瞄模块重写后由它负责填充。
#include "utils/common/type_common.hpp"

namespace aurora {

struct AimTargetHint {
    bool valid = false;
    TimePoint stamp {};
    int armor_id = -1;
    Vec3 position_in_big_yaw = Vec3::Zero();

    bool check() const noexcept {
        return valid;
    }
};

} // namespace aurora
