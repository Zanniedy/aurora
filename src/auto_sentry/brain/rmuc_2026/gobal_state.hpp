#pragma once
#include "auto_sentry/base/protocol_receive.hpp"
#include "utils/logger.hpp"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>

namespace aurora::sentry_brain {

class GobalState {
public:
    enum class SelfColor : bool { Red = 0, Blue = 1 } self_color;
    enum class Pose : uint8_t { UNKNOWEN = 0, Attack = 1, Defend = 2, Move = 3 } pose;
    static std::string Pose_to_str(Pose pose) {
        constexpr const char* details[] = { "Unknown", "Attack", "Defend", "Move" };
        return details[std::to_underlying(pose)];
    }
    std::unordered_map<uint8_t, int> pose_acc_time;
    std::unordered_map<uint8_t, int> last_pose_time;
    std::unordered_map<uint8_t, bool> pose_active_flags;
    GobalState() {
        pose_acc_time[std::to_underlying(Pose::UNKNOWEN)] = 0;
        pose_acc_time[std::to_underlying(Pose::Attack)] = 0;
        pose_acc_time[std::to_underlying(Pose::Defend)] = 0;
        pose_acc_time[std::to_underlying(Pose::Move)] = 0;
        last_pose_time[std::to_underlying(Pose::UNKNOWEN)] = 0;
        last_pose_time[std::to_underlying(Pose::Attack)] = 0;
        last_pose_time[std::to_underlying(Pose::Defend)] = 0;
        last_pose_time[std::to_underlying(Pose::Move)] = 0;
        pose_active_flags[std::to_underlying(Pose::UNKNOWEN)] = false;
        pose_active_flags[std::to_underlying(Pose::Attack)] = false;
        pose_active_flags[std::to_underlying(Pose::Defend)] = false;
        pose_active_flags[std::to_underlying(Pose::Move)] = false;
    }
    void update(const SentryRefereeReceive& d) {
        self_color = (d.robo_id > 100) ? SelfColor::Blue : SelfColor::Red;
        current_hp = d.current_hp;
        max_hp = d.max_hp;
        if (d.game_time < current_game_time_) {
            reset();
        }

        current_game_time_ = d.game_time;
        enemy_outpost_active_ = d.enemy_outpost_active;
        fort_allowance_bullets_ = d.fort_allowance_bullets;
        current_bullets_ = d.allowance_bullets;
        ally_outpost_hp_ = d.ally_outpost_hp;
        ally_base_hp_ = d.ally_base_hp;

        if (current_game_time_ >= 0) {
            update_pose(Pose(d.current_pose), current_game_time_);
            update_home_bullets(current_game_time_);
            update_remain_build_outpost_chance(ally_outpost_hp_, ally_base_hp_);
        } else {
            pose_acc_time[std::to_underlying(Pose::UNKNOWEN)] = 0;
            pose_acc_time[std::to_underlying(Pose::Attack)] = 0;
            pose_acc_time[std::to_underlying(Pose::Defend)] = 0;
            pose_acc_time[std::to_underlying(Pose::Move)] = 0;
            last_pose_time[std::to_underlying(Pose::UNKNOWEN)] = 0;
            last_pose_time[std::to_underlying(Pose::Attack)] = 0;
            last_pose_time[std::to_underlying(Pose::Defend)] = 0;
            last_pose_time[std::to_underlying(Pose::Move)] = 0;
            pose_active_flags[std::to_underlying(Pose::UNKNOWEN)] = false;
            pose_active_flags[std::to_underlying(Pose::Attack)] = false;
            pose_active_flags[std::to_underlying(Pose::Defend)] = false;
            pose_active_flags[std::to_underlying(Pose::Move)] = false;
        }
    }

    void update_pose(Pose new_pose, int game_time) {
        if (!pose_active_flags[std::to_underlying(new_pose)]) {
            pose_active_flags[std::to_underlying(new_pose)] = true;
            last_pose_time[std::to_underlying(new_pose)] = game_time;
            return;
        }
        pose_acc_time.at(std::to_underlying(new_pose)) +=
            std::abs(game_time - last_pose_time.at(std::to_underlying(new_pose)));
        if (pose_acc_time.at(std::to_underlying(new_pose)) > 170) {
            AURORA_WARN("need change pose");
        }
        last_pose_time.at(std::to_underlying(new_pose)) = game_time;
    }
    bool pose_active(Pose pose) {
        return pose_acc_time.at(std::to_underlying(pose)) < 170;
    }

    void update_home_bullets(int game_time) {
        int current_min = game_time / 60;

        if (current_min > last_min_) {
            int delta_min = current_min - last_min_;
            home_allowance_bullets_ += delta_min * 100;
            last_min_ = current_min;
        }
    }

    void update_remain_build_outpost_chance(int ally_outpost_hp, int ally_base_hp) {
        if (!ally_outpost_has_first_dead_) {
            if (ally_outpost_hp < last_ally_outpost_hp_) {
                if (ally_outpost_hp < 1) {
                    ally_outpost_has_first_dead_ = true;
                }
            }
            last_ally_outpost_hp_ = ally_outpost_hp;
            return;
        }

        if (last_base_hp_ - ally_base_hp >= 1000) {
            remain_rebuild_outpost_chance_++;
            last_base_hp_ = ally_base_hp;
        }

        if (ally_outpost_hp > last_ally_outpost_hp_) {
            if (ally_outpost_hp > 1450) {
                remain_rebuild_outpost_chance_--;
            }
        }

        last_ally_outpost_hp_ = ally_outpost_hp;

        remain_rebuild_outpost_chance_ = std::max(0, remain_rebuild_outpost_chance_);
    }

    void reset() {
        last_min_ = 0;
        home_allowance_bullets_ = 0;

        remain_rebuild_outpost_chance_ = 0;
        ally_outpost_has_first_dead_ = false;

        last_ally_outpost_hp_ = 0;
        last_base_hp_ = 5000;
        last_change_pose_time_ = 0;
    }


    //用来调试使用
    void mock_for_debug(){
         current_hp = max_hp;          // 满血
        current_game_time_ = 100;     // 假设比赛进行中
        ally_outpost_hp_ = 1500;      // 前哨战满血
        ally_base_hp_ = 5000;
        enemy_outpost_active_ = false;
        current_bullets_ = 200;
        AURORA_INFO("no serial no race just debug");
    }

    bool isdebug = false;
    int current_hp = 300;
    int max_hp = 400;
    int current_game_time_ = 0; //调试阶段 为0 正式比赛的时候为-1 等待比赛的开始
    int fort_allowance_bullets_ = 0;
    int home_allowance_bullets_ = 0;
    int current_bullets_ = 0;
    int remain_rebuild_outpost_chance_ = 0;
    int ally_base_hp_ = 0;
    int ally_outpost_hp_ = 0;
    bool enemy_outpost_active_ = false;

private:
    int last_min_ = 0;
    int last_ally_outpost_hp_ = 0;
    int last_base_hp_ = 5000;
    int last_change_pose_time_ = 0;
    bool ally_outpost_has_first_dead_ = false;
};

} // namespace aurora::sentry_brain