#pragma once
#include "utils/impl.hpp"
#include "utils/net_detector/net_detector_base.hpp"
namespace aurora::utils {
class NetDetectorTensorrt: public NetDetectorBase {
public:
    NetDetectorTensorrt(const YAML::Node& config, Config c);
    [[nodiscard]] OutPut detect(const cv::Mat& img, PixelFormat format) noexcept override;
    AURORA_IMPL_DEFINITION(NetDetectorTensorrt)
};

} // namespace aurora::utils