#include "auto_sentry/brain/rmuc_2026/map.hpp"
#include "utils/logger.hpp"
#include "utils/utils.hpp"
#include <optional>
#include <string>
using namespace aurora::sentry_brain;
int main(int argc, char** argv) {
    aurora::logger::init(spdlog::level::trace);
    auto& map = RMUC2026Map::instance();
    auto second_arg = aurora::utils::get_arg(2, argc, argv);
    if (second_arg) {
        map.load_points_yaml(second_arg.value());
    }
    map.load_ros_map_yaml(aurora::utils::get_arg(1, argc, argv).value());
    map.visualize();
    map.dump_yaml(second_arg.value_or("output/rmuc_2026_map_point.yaml"));
}