#pragma once
// 统一走 aurora_logger，同时保留 logger::init(level) 的调用习惯。
#include "log.hpp"

#include <string>

namespace aurora::logger {

inline void init(spdlog::level::level_enum level) {
    aurora::init_logger(level);
}

} // namespace aurora::logger
