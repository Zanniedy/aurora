#include "auto_sentry/aim/armor_detect/armor_detector.hpp"
#include "param_deliver.h"
#include "utils/logger.hpp"
#include "utils/utils.hpp"

#include <iostream>
#include <filesystem>
#include <yaml-cpp/yaml.h>

int main(int argc, char** argv) {
    aurora::logger::init(spdlog::level::info);
    auto config_path = aurora::utils::get_arg(1, argc, argv);
    if (!config_path) {
        std::cerr << "usage: auto_aim_probe <sentry.yaml>\n";
        return 2;
    }

    try {
        auto config = YAML::LoadFile(config_path.value());
        const auto detector = config["armor_detector"];
        const auto model = detector["net_detector"]["openvino"]["model_path"];
        if (model) {
            const auto path = replace_root_dir(model.as<std::string>());
            if (!std::filesystem::exists(path)) {
                std::cerr << "missing armor model: " << path << '\n';
                return 1;
            }
        }
        std::cout << "auto-aim configuration is readable\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "auto-aim configuration check failed: " << error.what() << '\n';
        return 1;
    }
}
