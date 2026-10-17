#pragma once
#include "auto_sentry/aim/type.hpp"
#include "utils/impl.hpp"
#include <optional>
#include <vector>
namespace aurora::auto_aim {

    //定义装甲板的识别类
class ArmorDetector {
public:
    using Ptr = std::unique_ptr<ArmorDetector>;
    ArmorDetector(const YAML::Node& config);
    [[nodiscard]] std::tuple<std::vector<Light>, std::vector<Armor>> detect(
        const CommonFrame& frame,
        const cv::Rect& net_focus,
        const std::optional<cv::Rect>& detect_light = std::nullopt
    );
    double get_net_wh_ratio() const noexcept;
    AURORA_IMPL_DEFINITION(ArmorDetector)
};
} // namespace aurora::auto_aim