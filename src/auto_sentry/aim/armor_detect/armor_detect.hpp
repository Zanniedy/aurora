#pragma once 


#include <memory>
#include <yaml
namespace aurora::auto_aim {

class  ArmorDetector {
    public:
        using Ptr = std::unique_ptr<ArmorDetector>;
        ArmorDetector(const YAML::Node& config)
}

}