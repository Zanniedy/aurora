#pragma once
// 作为轻量调试输出；当前没有独立的调试面板，先把结构化数据打到 trace 日志。
#include "utils/logger.hpp"

#include <nlohmann/json.hpp>
#include <string_view>

namespace aurora::debug {

template<typename T>
inline auto val(const T& v) {
    return v;
}

template<typename Fn>
inline void write_log(std::string_view name, Fn&& fill) {
    auto logger = ::aurora::logger::get_logger();
    if (!logger->should_log(spdlog::level::trace)) {
        return;
    }
    nlohmann::json j;
    fill(j);
    AURORA_TRACE("[{}] {}", name, j.dump());
}

} // namespace aurora::debug
