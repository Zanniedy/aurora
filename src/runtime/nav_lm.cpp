#include "backward-cpp/backward.hpp"
#include "navigation/lm/small_point_lio.hpp"

#include <rclcpp/rclcpp.hpp>

// 原 rose_navigation 的 rclcpp_components 节点，单体工程里直接作为独立进程。
namespace aurora::nav {
class SmallPointLioNode: public rclcpp::Node {
public:
    explicit SmallPointLioNode(const rclcpp::NodeOptions& options): Node("rose_nav_lm", options) {
        small_point_lio = std::make_unique<lm::SmallPointLIO>(*this);
    }
    std::unique_ptr<lm::SmallPointLIO> small_point_lio;
};
} // namespace aurora::nav

int main(int argc, char** argv) {
    backward::SignalHandling sh;
    rclcpp::init(argc, argv);
    auto node = std::make_shared<aurora::nav::SmallPointLioNode>(rclcpp::NodeOptions());
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
