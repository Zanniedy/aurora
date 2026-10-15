#pragma once

#include <cstddef>
#include <memory>
#include <string>

#include <spdlog/spdlog.h>

namespace aurora::logger {

struct InitOptions {
    std::string folder_path;
    spdlog::level::level_enum level = spdlog::level::info;
    std::size_t max_file_size = 10 * 1024 * 1024;
    std::size_t max_files = 3;
    std::size_t folder_warn_size = 50 * 1024 * 1024;
};

std::shared_ptr<spdlog::logger> get_logger();
void init(const InitOptions& options);
void init(
    const std::string& folder_path,
    spdlog::level::level_enum level = spdlog::level::info
);
void shutdown();
void flush();
void set_level(spdlog::level::level_enum level);
bool initialized();
std::string get_current_log_file_path();

} // namespace aurora::logger

namespace aurora {

std::string default_log_folder();
void init_logger(spdlog::level::level_enum level = spdlog::level::info);
void init_logger(
    const std::string& folder_path,
    spdlog::level::level_enum level = spdlog::level::info
);

} // namespace aurora
