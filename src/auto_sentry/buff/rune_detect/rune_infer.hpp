#pragma once
#include "auto_sentry/buff/type.hpp"
#include "utils/common/image.hpp"
#include "utils/impl.hpp"
namespace aurora::auto_buff {
class RuneInfer {
public:
    using Ptr = std::unique_ptr<RuneInfer>;
    RuneInfer(const YAML::Node& config);
    AURORA_IMPL_DEFINITION(RuneInfer)
    static Ptr create(const YAML::Node& config) {
        return std::make_unique<RuneInfer>(config);
    }

    [[nodiscard]] std::vector<RuneFanBladeWithR> process(const cv::Mat& output_buffer) const;

    int input_w() const noexcept;
    int input_h() const noexcept;
    bool use_norm() const noexcept;
    PixelFormat target_format() const noexcept;
};

} // namespace aurora::auto_buff