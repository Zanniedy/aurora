#pragma once
#include "navigation/map/rose_map.hpp"
#include "navigation/planner/common.hpp"
#include "navigation/planner/traj.hpp"
#include "navigation/utils/rclcpp_parameter_node.hpp"
#include <memory>
namespace aurora::nav::planner {
class LMPC {
public:
    using Ptr = std::unique_ptr<LMPC>;
    LMPC(map::RoseMap::Ptr rose_map, const ParamsNode& config);
    static Ptr create(map::RoseMap::Ptr rose_map, const ParamsNode& config) {
        return std::make_unique<LMPC>(rose_map, config);
    }
    std::optional<ControlOutput> solve(std::chrono::duration<double> dt);
    void set_traj(const Traj& traj);
    void set_current(const RoboState& c);
    ~LMPC();
    struct Impl;
    std::unique_ptr<Impl> _impl;
};
} // namespace aurora::nav::planner