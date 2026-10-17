#include "backward-cpp/backward.hpp"
#include "navigation/map/rose_map.hpp"

#include <rclcpp/rclcpp.hpp>

// 原 rose_navigation 的 rclcpp_components 节点，单体工程里直接作为独立进程。
namespace aurora::nav {
class RoseMapNode: public rclcpp::Node {
public:
    explicit RoseMapNode(const rclcpp::NodeOptions& options): Node("rose_nav_map", options) {
        rose_map = std::make_unique<map::RoseMap>(*this);
    }
    std::unique_ptr<map::RoseMap> rose_map;
};
} // namespace aurora::nav

int main(int argc, char** argv) {
    backward::SignalHandling sh;
    rclcpp::init(argc, argv);
    auto node = std::make_shared<aurora::nav::RoseMapNode>(rclcpp::NodeOptions());
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
