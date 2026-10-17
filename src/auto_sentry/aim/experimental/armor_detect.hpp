#pragma once 


#include "type.hpp"

#include <memory>
#include <opencv2/core/types.hpp>
#include <optional>
#include <tuple>
#include <vector>
#include <yaml-cpp/node/detail/node_iterator.h>
#include <yaml-cpp/yaml.h>
namespace aurora::auto_aim {

class  ArmorDetector {
    public:
        using Ptr = std::unique_ptr<ArmorDetector>;
        ArmorDetector(const YAML::Node& config);
        [[nodicard]] std::tuple<std::vector<Light> ,std::vector <Armor>>detect (
        const CommonFrames& frame ,
        const cv::Rect& net_focus ,
        const std::optional<cv::Rect>& detect_light = std::nullopt);
    
    double get_net_wh_ratio() const noexcept ;

};
    
}