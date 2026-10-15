#include "log.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

static int g_failed = 0;
static int g_passed = 0;

#define REQUIRE(cond)                                                          \
    do {                                                                       \
        if (cond) {                                                            \
            ++g_passed;                                                        \
        } else {                                                               \
            std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << " "         \
                      << #cond << '\n';                                        \
            ++g_failed;                                                        \
        }                                                                      \
    } while (0)

static std::string read_file(const fs::path& path) {
    std::ifstream in(path);
    std::ostringstream oss;
    oss << in.rdbuf();
    return oss.str();
}

static fs::path make_temp_dir() {
    const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
    auto dir = fs::temp_directory_path() / ("aurora_logger_test_" + std::to_string(stamp));
    fs::remove_all(dir);
    fs::create_directories(dir);
    return dir;
}

static void test_fallback_before_init() {
    aurora::logger::shutdown();
    REQUIRE(!aurora::logger::initialized());
    REQUIRE(aurora::logger::get_logger() != nullptr);
    REQUIRE(aurora::logger::get_current_log_file_path().empty());
    AURORA_INFO("fallback logger should not crash");
}

static void test_init_writes_file() {
    const auto dir = make_temp_dir();
    aurora::logger::shutdown();
    aurora::logger::init(dir.string(), spdlog::level::debug);
    REQUIRE(aurora::logger::initialized());

    const auto log_file = aurora::logger::get_current_log_file_path();
    REQUIRE(!log_file.empty());
    REQUIRE(fs::exists(log_file));

    AURORA_INFO("hello {}", "aurora");
    aurora::logger::flush();

    const auto content = read_file(log_file);
    REQUIRE(content.find("hello aurora") != std::string::npos);
    REQUIRE(content.find("Logger initialized") != std::string::npos);

    aurora::logger::shutdown();
    fs::remove_all(dir);
}

static void test_double_init_is_noop() {
    const auto dir = make_temp_dir();
    aurora::logger::shutdown();
    aurora::logger::init(dir.string(), spdlog::level::info);
    const auto first = aurora::logger::get_current_log_file_path();

    aurora::logger::init(dir.string(), spdlog::level::debug);
    const auto second = aurora::logger::get_current_log_file_path();
    REQUIRE(first == second);
    REQUIRE(aurora::logger::get_logger()->level() == spdlog::level::info);

    aurora::logger::shutdown();
    fs::remove_all(dir);
}

static void test_shutdown_allows_reinit() {
    const auto dir = make_temp_dir();
    aurora::logger::shutdown();
    aurora::logger::init(dir.string(), spdlog::level::info);
    aurora::logger::shutdown();
    REQUIRE(!aurora::logger::initialized());

    aurora::logger::init(dir.string(), spdlog::level::debug);
    REQUIRE(aurora::logger::initialized());
    REQUIRE(aurora::logger::get_logger()->level() == spdlog::level::debug);

    aurora::logger::shutdown();
    fs::remove_all(dir);
}

static void test_set_level_and_macros() {
    const auto dir = make_temp_dir();
    aurora::logger::shutdown();
    aurora::logger::init(dir.string(), spdlog::level::info);

    const auto log_file = aurora::logger::get_current_log_file_path();
    AURORA_DEBUG("hidden-debug");
    aurora::logger::flush();
    REQUIRE(read_file(log_file).find("hidden-debug") == std::string::npos);

    aurora::logger::set_level(spdlog::level::debug);
    AURORA_DEBUG("visible-debug");
    aurora::logger::flush();
    REQUIRE(read_file(log_file).find("visible-debug") != std::string::npos);

    aurora::logger::shutdown();
    fs::remove_all(dir);
}

static void test_folder_cleanup() {
    const auto dir = make_temp_dir();
    const auto old_log = dir / "old.log";
    {
        std::ofstream out(old_log, std::ios::binary);
        std::string payload(4096, 'x');
        out << payload;
    }
    fs::last_write_time(old_log, fs::file_time_type::clock::now() - std::chrono::hours(1));

    aurora::logger::InitOptions options;
    options.folder_path = dir.string();
    options.level = spdlog::level::info;
    options.folder_warn_size = 1024;
    aurora::logger::shutdown();
    aurora::logger::init(options);
    aurora::logger::flush();

    REQUIRE(!fs::exists(old_log));
    REQUIRE(aurora::logger::initialized());

    aurora::logger::shutdown();
    fs::remove_all(dir);
}

int main() {
    test_fallback_before_init();
    test_init_writes_file();
    test_double_init_is_noop();
    test_shutdown_allows_reinit();
    test_set_level_and_macros();
    test_folder_cleanup();

    std::cout << "passed=" << g_passed << " failed=" << g_failed << '\n';
    return g_failed == 0 ? 0 : 1;
}
