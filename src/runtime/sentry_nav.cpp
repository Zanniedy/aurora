#include "ascii_banner.hpp"
#include "backward-cpp/backward.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "auto_sentry/brain/rmuc_2026/mode_factory.hpp"
#include "utils/signal_guard.hpp"
using namespace aurora;
namespace backward {
static backward::SignalHandling sh;
}
struct SerialTag {};
using SerialIO = IOPair<SerialTag, std::vector<uint8_t>>;


//调试导航
int main(int argc, char** argv) {
    print_banner();
    auto& signal = utils::SignalGuard::instance();
    logger::init(spdlog::level::trace);

    std::string config_path;
    auto first_arg = utils::get_arg(1, argc, argv);
    if (first_arg) {
        config_path = first_arg.value();
    } else {
        return 1;
    }
    // 第二个参数为 brain 时才启用决策，否则只转发 cmd_vel，目标点由 rviz2 发布到 /rose_goal
    auto second_arg = utils::get_arg(2, argc, argv);
    bool use_brain = second_arg && second_arg.value() == "brain";
    auto config = YAML::LoadFile(config_path);
    Scheduler s;
    std::shared_ptr<SerialDriver> serial = std::make_shared<SerialDriver>(config["serial"], s);
    rcl::RclcppNode rcl_node("nav");
    rcl::TF rcl_tf(rcl_node);
    std::unique_ptr<sentry_brain::ModeBase> brain;
    if (use_brain) {
        brain = sentry_brain::create_brain_mode(rcl_node, rcl_tf, config["brain"], serial);
    }
    AURORA_INFO("nav brain: {}", brain ? "enabled" : "disabled (manual goal from rviz2)");
    s.register_task<SerialIO>("receive_serial", [&](SerialIO::second_type&& data) {
        auto robo_opt = ReceiveRobotData::create(data);
        if (robo_opt.has_value()) {
            auto robo = robo_opt.value();
            robo.update_log(0);
        }
        //获取到关节的串口讯息
        auto joint_opt = SentryJointState::create(data);
        if (joint_opt.has_value()) {
            auto joint = joint_opt.value();
            joint.update_log();
        }
        auto referee_opt = SentryRefereeReceive::create(data);
        if (referee_opt) {
            referee_opt->update_log();
            if (brain) {
                brain->update_gobal_state(referee_opt.value());
            }
        }
    });
    auto cmd_sub = rcl_node.make_sub<geometry_msgs::msg::Twist>(
        "cmd_vel",
        rclcpp::QoS(10),
        [&](const geometry_msgs::msg::Twist::SharedPtr msg) {
            SendNavCmdData send;

            send.cmd_ID = SendNavCmdData::ID;
            send.vx = msg->linear.x;
            send.vy = msg->linear.y;
            send.wz = msg->angular.z;
            send.turtle_state = (msg->linear.z > 0) ? true : false;
            serial->write(utils::to_vector(send));
        }
    );
    rcl_node.push_sub(cmd_sub);
    serial->start<SerialTag>("serial");
    if (brain) {
        brain->start();
    }
    s.build();
    s.run();
    std::thread([&]() { rcl_node.spin(); }).detach();
    utils::SignalGuard::spin(std::chrono::milliseconds(1000));
    s.stop();

    rcl_node.shutdown();

    return 0;
}