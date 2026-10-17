#include "backward-cpp/backward.hpp"
#include "navigation/planner/rose_planner.hpp"

#include <rclcpp/rclcpp.hpp>

// 原 rose_navigation 的 rclcpp_components 节点，单体工程里直接作为独立进程。
namespace aurora::nav {
class RosePlannerNode: public rclcpp::Node {
public:
    explicit RosePlannerNode(const rclcpp::NodeOptions& options): Node("rose_nav_planner", options) {
        rose_planner = std::make_unique<planner::RosePlanner>(*this);
    }
    std::unique_ptr<planner::RosePlanner> rose_planner;
};
} // namespace aurora::nav

int main(int argc, char** argv) {
    backward::SignalHandling sh;
    rclcpp::init(argc, argv);
    auto node = std::make_shared<aurora::nav::RosePlannerNode>(rclcpp::NodeOptions());
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
