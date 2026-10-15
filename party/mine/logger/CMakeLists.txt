cmake_minimum_required(VERSION 3.14)

# 必须在 project() 之前打开，cmake 扩展和 make.sh 都会用到这份数据库。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

project(aurora_logger CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 发行版的 spdlog 1.9 和本机 fmt 12 不兼容，固定用自带 fmt 的 v1.15.3。
# 已经装到 CMAKE_PREFIX_PATH / third_party 的兼容版本仍然优先。
find_package(spdlog 1.15 QUIET)
if(NOT TARGET spdlog::spdlog)
    message(STATUS "Compatible spdlog not found, fetching v1.15.3")
    set(SPDLOG_FMT_EXTERNAL OFF CACHE BOOL "" FORCE)
    set(SPDLOG_INSTALL OFF CACHE BOOL "" FORCE)
    include(FetchContent)
    FetchContent_Declare(
        spdlog
        GIT_REPOSITORY https://github.com/gabime/spdlog.git
        GIT_TAG        v1.15.3
    )
    FetchContent_MakeAvailable(spdlog)
else()
    message(STATUS "Using spdlog >= 1.15: ${spdlog_DIR}")
endif()

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
