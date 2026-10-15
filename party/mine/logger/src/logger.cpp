#include "logger.hpp"
#include "logger_utils.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <vector>

#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>

namespace aurora::logger {
namespace {

std::shared_ptr<spdlog::logger>& active_logger() {
    static std::shared_ptr<spdlog::logger> logger;
    return logger;
}

std::mutex& init_mutex() {
    static std::mutex mutex;
    return mutex;
}

std::shared_ptr<spdlog::logger>& fallback_logger() {
    static auto logger = [] {
        auto sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
        sink->set_pattern("[%H:%M:%S.%e] [%^%l%$] %v");
        auto fallback = std::make_shared<spdlog::logger>(detail::LOG_NAME, sink);
        fallback->set_level(spdlog::level::trace);
        fallback->flush_on(spdlog::level::warn);
        return fallback;
    }();
    return logger;
}

} // namespace

std::shared_ptr<spdlog::logger> get_logger() {
    std::lock_guard<std::mutex> lock(init_mutex());
    auto& logger = active_logger();
    return logger ? logger : fallback_logger();
}

std::string get_current_log_file_path() {
    std::lock_guard<std::mutex> lock(init_mutex());
    auto& logger = active_logger();
    if (!logger) {
        return {};
    }

    for (const auto& sink : logger->sinks()) {
        if (auto file_sink =
                std::dynamic_pointer_cast<spdlog::sinks::rotating_file_sink_mt>(sink)) {
            return file_sink->filename();
        }
    }
    return {};
}

void init(const InitOptions& options) {
    std::lock_guard<std::mutex> lock(init_mutex());
    if (active_logger()) {
        return;
    }

    InitOptions resolved = options;
    if (resolved.folder_path.empty()) {
        resolved.folder_path = aurora::default_log_folder();
    }
    if (resolved.max_file_size == 0) {
        resolved.max_file_size = 10 * 1024 * 1024;
    }
    if (resolved.max_files == 0) {
        resolved.max_files = 3;
    }

    try {
        std::filesystem::create_directories(resolved.folder_path);

        const std::string file_path = detail::generate_log_filename(resolved.folder_path);

        auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
        console_sink->set_pattern("[%H:%M:%S.%e] [%^%l%$] [%s:%#] %v");

        auto file_sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
            file_path, resolved.max_file_size, static_cast<std::size_t>(resolved.max_files)
        );
        file_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%l] [%s:%#] %v");

        std::vector<spdlog::sink_ptr> sinks{console_sink, file_sink};
        auto logger = std::make_shared<spdlog::logger>(
            detail::LOG_NAME, sinks.begin(), sinks.end()
        );
        logger->set_level(resolved.level);
        logger->flush_on(spdlog::level::warn);

        if (!spdlog::get(detail::LOG_NAME)) {
            spdlog::register_logger(logger);
        }

        active_logger() = logger;
        detail::check_folder_size(
            resolved.folder_path, resolved.folder_warn_size, file_path, logger
        );
        logger->info("Logger initialized. Log file: {}", file_path);
    } catch (const spdlog::spdlog_ex& ex) {
        std::cerr << "Logger init failed: " << ex.what() << std::endl;
    } catch (const std::filesystem::filesystem_error& ex) {
        std::cerr << "Logger filesystem error: " << ex.what() << std::endl;
    }
}

void init(const std::string& folder_path, spdlog::level::level_enum level) {
    InitOptions options;
    options.folder_path = folder_path;
    options.level = level;
    init(options);
}

void shutdown() {
    std::lock_guard<std::mutex> lock(init_mutex());
    auto& logger = active_logger();
    if (!logger) {
        return;
    }
    logger->flush();
    spdlog::drop(detail::LOG_NAME);
    logger.reset();
}

void flush() {
    get_logger()->flush();
}

void set_level(spdlog::level::level_enum level) {
    auto logger = get_logger();
    logger->set_level(level);
}

bool initialized() {
    std::lock_guard<std::mutex> lock(init_mutex());
    return static_cast<bool>(active_logger());
}

} // namespace aurora::logger

namespace aurora {

std::string default_log_folder() {
    const char* home = std::getenv("HOME");
    return std::string(home ? home : ".") + "/.aurora/log";
}

void init_logger(spdlog::level::level_enum level) {
    aurora::logger::init(default_log_folder(), level);
}

void init_logger(const std::string& folder_path, spdlog::level::level_enum level) {
    aurora::logger::init(folder_path, level);
}

} // namespace aurora
