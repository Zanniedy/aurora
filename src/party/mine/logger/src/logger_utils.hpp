#pragma once

#include <algorithm>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <memory>
#include <sstream>
#include <string>
#include <system_error>
#include <vector>

#include <spdlog/spdlog.h>

namespace aurora::logger::detail {

inline constexpr auto LOG_NAME = "aurora";

inline std::string generate_log_filename(const std::string& folder_path) {
    const auto now = std::chrono::system_clock::now();
    const auto t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#ifdef _WIN32
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif

    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                        now.time_since_epoch()
                    ) % 1000;

    std::ostringstream oss;
    oss << folder_path << '/' << std::put_time(&tm, "%Y-%m-%d_%H-%M-%S") << '_'
        << std::setfill('0') << std::setw(3) << ms.count() << ".log";
    return oss.str();
}

inline void check_folder_size(
    const std::string& folder_path,
    std::size_t warn_size,
    const std::string& current_log,
    const std::shared_ptr<spdlog::logger>& logger
) {
    std::error_code ec;
    if (!std::filesystem::exists(folder_path, ec)) {
        return;
    }

    struct LogFile {
        std::filesystem::path path;
        std::filesystem::file_time_type write_time;
        std::uintmax_t size = 0;
    };

    std::vector<LogFile> files;
    std::uintmax_t total_size = 0;
    const auto current_path = std::filesystem::path(current_log);

    for (const auto& entry : std::filesystem::directory_iterator(folder_path, ec)) {
        if (!entry.is_regular_file(ec)) {
            continue;
        }

        const auto size = entry.file_size(ec);
        if (ec) {
            ec.clear();
            continue;
        }

        total_size += size;
        if (entry.path() == current_path) {
            continue;
        }

        const auto write_time = entry.last_write_time(ec);
        if (ec) {
            ec.clear();
            continue;
        }
        files.push_back({entry.path(), write_time, size});
    }

    if (total_size < warn_size || !logger) {
        return;
    }

    logger->warn(
        "Log folder {} size {} bytes exceeds warning threshold {} bytes, deleting old logs",
        folder_path,
        total_size,
        warn_size
    );

    std::sort(files.begin(), files.end(), [](const LogFile& a, const LogFile& b) {
        return a.write_time < b.write_time;
    });

    const auto target_free_size = total_size / 2;
    std::uintmax_t removed_size = 0;
    for (const auto& file : files) {
        if (removed_size >= target_free_size) {
            break;
        }
        std::filesystem::remove(file.path, ec);
        if (!ec) {
            removed_size += file.size;
        } else {
            logger->warn(
                "Failed to remove old log {}: {}",
                file.path.string(),
                ec.message()
            );
            ec.clear();
        }
    }

    logger->warn(
        "Log folder cleanup removed {} bytes, remaining about {} bytes",
        removed_size,
        total_size - removed_size
    );
}

} // namespace aurora::logger::detail
