#pragma once
#include "rcl/node.hpp"
#include "rcl/tf.hpp"
#include "mode_base.hpp"
#include "auto_sentry/base/protocol_send.hpp"
#include "auto_sentry/brain/rmuc_2026/gobal_state.hpp"
#include "auto_sentry/brain/rmuc_2026/map.hpp"
#include "utils/drivers/serial_driver.hpp"
#include "utils/impl.hpp"
#include "utils/logger.hpp"
#include <memory>
#include <optional>

namespace aurora::sentry_brain {

class HomeMode: public ModeBase {
public:
    struct Params {
        double go_home_hp_ratio;
        int home_bullet_num;

        void load(const YAML::Node& config) {
            go_home_hp_ratio = config["go_home_hp_ratio"].as<double>();
            home_bullet_num = config["home_bullet_num"].as<int>();
        }
    } params_;

    HomeMode(
        rcl::RclcppNode& rcl_node,
        rcl::TF& rcl_tf,
        const YAML::Node& config,
        std::shared_ptr<SerialDriver> serial
    ):
        ModeBase(rcl_node, rcl_tf, config, serial) {
        params_.load(config);
        
        //公用一个串口 
        if(serial_){
            state_.mock_for_debug();
        }
    }

    struct Action {
        GobalState::Pose pose;
        std::optional<Eigen::Vector2d> goal;
        std::string goal_name;
    };

private:
//设定当前的位置状态
    void send_current_pose() {
        if (!serial_)
            return;
        SentryRefereeSend send;
        send.cmd_ID = SentryRefereeSend::ID;
        send.set_current_pose = std::to_underlying(sentry_pose);
        AURORA_INFO("SEND: {}", GobalState::Pose_to_str(sentry_pose));
    }

    //判断是否到达相应的目标点
    template<typename Key>
    Action make_move_action(GobalState::Pose arrived_pose = GobalState::Pose::Defend) {
        go<Key>();
        if (!is_reached<Key>())
            return { GobalState::Pose::Move, current_goal_, Key::name };
        return { arrived_pose, current_goal_, Key::name };
    }

    bool low_hp() const {
        double ratio = double(state_.current_hp) / state_.max_hp;
        return (ratio < params_.go_home_hp_ratio || state_.current_hp < 60);
    }
//定义底血状态的动作
    Action low_hp_action() {
        wait_until(
            [this]() {
                auto action = make_move_action<home_t>();
                sentry_pose = action.pose;
                send_current_pose();
                if (std::abs(state_.current_hp - state_.max_hp) < 50) {
                    AURORA_INFO("hp is enough: {}", state_.current_hp);
                    return true;
                }
                if (state_.current_hp < 10)
                    sentry_pose = GobalState::Pose::Defend;
                this->send_current_pose();
                AURORA_INFO("waiting for hp to recover: {}", state_.current_hp);
                return false;
            },
            std::chrono::duration<double>(0.3)
        );
        return make_move_action<home_t>();
    }

    bool low_bullet() const {
        return state_.current_bullets_ < params_.home_bullet_num;
    }

    //允许发弹量
    Action low_bullet_action() {
        if (state_.home_allowance_bullets_ > 10)
            return make_move_action<home_t>();
        else
            return make_move_action<ally_fort_t>();
    }
    Action hit_outpost_action() {
        Action a;
        AURORA_INFO("enemy_outpost_active!");
        a = make_move_action<ally_best_hit_outpost_t>();
        if (target_in_big_yaw_.check()) {
            a.pose = GobalState::Pose::Attack;
        }
        return a;
    }

    //巡逻的动作
    Action patrol_action() {
        if (!target_in_big_yaw_.check()) {
            patrol<ally_best_hit_outpost_t, ally_second_step_bottom_t>(20.0);
            if (!is_reached<ally_best_hit_outpost_t>() && !is_reached<ally_second_step_bottom_t>())
            {
                return { GobalState::Pose::Move, current_goal_, "Patrol" };
            }
            return { GobalState::Pose::Defend, current_goal_, "Patrol_reached" };
        }
        return { GobalState::Pose::Attack, current_pos_, "Stop" };
    }
    Action fort_action() {
        Action a;
        a = make_move_action<ally_fort_t>();
        if (target_in_big_yaw_.check()) {
            a.pose = GobalState::Pose::Attack;
        }
        return a;
    }
    Action help_outpost_action() {
        Action a;
        a = make_move_action<ally_second_step_bottom_t>();
        if (target_in_big_yaw_.check()) {
            a.pose = GobalState::Pose::Attack;
        }
        return a;
    }

public:

//启动比赛的回调函数
    void tick_callback() override {
        send_current_pose();

        auto& map = RMUC2026Map::instance();

        if(state_.isdebug){
            if (state_.current_game_time_ < 0) {
            AURORA_INFO("waiting for game start... current_time: {}", state_.current_game_time_);
            return;
        }}
        
        else {
        state_.mock_for_debug();
        AURORA_INFO("caurrent_hp",state_.current_hp);
        }


        //相关的决策逻辑
        if (in_home())
            state_.home_allowance_bullets_ = 0;

        std::optional<Action> action;

        // 优先级决策
        if (low_hp())
            action = low_hp_action();
        if (!action && low_bullet())
            action = low_bullet_action();
        if (!action && state_.enemy_outpost_active_) {
            action = hit_outpost_action();
        }
        if (!action && state_.ally_outpost_hp_ > 10) {
            action = help_outpost_action();
        }
        if (!action && state_.ally_outpost_hp_ < 1) {
            action = fort_action();
        }

        if (!action) {
            action = patrol_action();
        }
        if (action) {
            sentry_pose = action->pose;
            current_goal_ = action->goal;
            current_goal_name_ = action->goal_name;
        }
        // 目标检测覆盖
        if (target_in_big_yaw_.check())
            sentry_pose = GobalState::Pose::Attack;

        // 极低血量保护
        if (state_.current_hp < 10)
            sentry_pose = GobalState::Pose::Defend;
    }
};

} // namespace aurora::sentry_brain