#pragma once

#include "auto_sentry/aim/armor_track/armor_target.hpp"
#include "auto_sentry/aim/auto_aim_fsm.hpp"
#include "auto_sentry/aim/type.hpp"
#include "auto_sentry/buff/rune_track/rune_target.hpp"
#include "auto_sentry/buff/type.hpp"
#include "auto_sentry/base/common.hpp"
#include "utils/debug_log.hpp"
#include "utils/buffer.hpp"

#include <opencv2/core/mat.hpp>
#include <utility>

namespace aurora {

class Web {
public:
    using VisionDebugCtx = struct {
        CameraInfo camera_info_;
        utils::Locked<ImageFrame> img_frame;
        utils::Locked<cv::Rect2f> expanded;
        utils::Locked<double> avg_latency_ms;
        utils::Locked<GimbalCmd> gimbal_cmd;
        utils::Locked<std::pair<double, double>> gimbal_yaw_pitch;
        utils::Locked<std::vector<Vec3>> bullet_positions;
        utils::Locked<ISO3> odom_in_camera_cv;
        enum Type { AUTO_AIM, AUTO_BUFF } type = AUTO_AIM;
        utils::Locked<auto_aim::Armors> armors;
        utils::Locked<auto_aim::ArmorTarget> armor_target;
        utils::Locked<auto_aim::AutoAimFsm> auto_aim_fsm_state;
        utils::Locked<auto_buff::RuneDetection> rune;
        utils::Locked<auto_buff::RuneTarget> rune_target;
    };

    template<typename T>
    static auto val(const T& value) {
        return debug::val(value);
    }

    template<typename Fn>
    static void write_log(const char* name, Fn&& fill) {
        debug::write_log(name, std::forward<Fn>(fill));
    }

    void draw(cv::Mat&, const VisionDebugCtx&) const noexcept {}
    void write_debug_data(const VisionDebugCtx&) const noexcept {}
    void write_shm(const cv::Mat&) const noexcept {}
};

using VisionDebugCtx = Web::VisionDebugCtx;

} // namespace aurora
