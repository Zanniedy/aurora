#pragma once
#include "../net_detector_base.hpp"
#include "utils/impl.hpp"
namespace aurora::utils {
class NetDetectorOpenVINO: public NetDetectorBase {
public:
    NetDetectorOpenVINO(const YAML::Node& config, Config c);
    [[nodiscard]] OutPut detect(const cv::Mat& img, PixelFormat format) noexcept override;
    AURORA_IMPL_DEFINITION(NetDetectorOpenVINO)
};
} // namespace aurora::utils