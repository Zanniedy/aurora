#include "log.hpp"

int main() {
    aurora::logger::init("log", spdlog::level::debug);

    AURORA_TRACE("trace message {}", 1);
    AURORA_DEBUG("debug message {}", 2);
    AURORA_INFO("aurora logger example start");
    AURORA_WARN("warn message");
    AURORA_ERROR("error message");

    aurora::logger::flush();
    AURORA_INFO("log file: {}", aurora::logger::get_current_log_file_path());
    aurora::logger::shutdown();
    return 0;
}
