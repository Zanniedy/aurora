cmake_minimum_required(VERSION 3.14)

project(aurora_logger CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.15.3
)
FetchContent_MakeAvailable(spdlog)

# ── library ───────────────────────────────────────────────────────────────────

add_library(aurora_logger STATIC
    src/logger.cpp
)

target_include_directories(aurora_logger PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
)

target_link_libraries(aurora_logger PUBLIC spdlog::spdlog)

# ── example ───────────────────────────────────────────────────────────────────

add_executable(aurora_logger_example
    example/main.cpp
)

target_link_libraries(aurora_logger_example PRIVATE aurora_logger)

# ── tests ─────────────────────────────────────────────────────────────────────

enable_testing()

add_executable(aurora_logger_test
    test/test_logger.cpp
)

target_link_libraries(aurora_logger_test PRIVATE aurora_logger)

add_test(NAME aurora_logger_test COMMAND aurora_logger_test)
