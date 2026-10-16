cmake_minimum_required(VERSION 3.14)

# 必须在 project() 之前打开，cmake 扩展和 make.sh 都会用到这份数据库。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

project(aurora_logger VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

# 发行版的 spdlog 1.9 和本机 fmt 12 不兼容，需要 >= 1.15。
# 找到的必须是已安装的导入目标；源码拉下来的 spdlog 单独安装，避免和本库的
# install(EXPORT) 缠在同一个构建里。
find_package(spdlog 1.15 QUIET)
if(NOT TARGET spdlog::spdlog)
    message(STATUS "Compatible spdlog not found, building v1.15.3")
    include(FetchContent)
    FetchContent_Declare(
        spdlog
        GIT_REPOSITORY https://github.com/gabime/spdlog.git
        GIT_TAG        v1.15.3
    )
    FetchContent_GetProperties(spdlog)
    if(NOT spdlog_POPULATED)
        FetchContent_Populate(spdlog)
    endif()

    set(_AURORA_SPDLOG_BUILD "${CMAKE_BINARY_DIR}/spdlog-external")
    set(_AURORA_SPDLOG_PREFIX "${CMAKE_BINARY_DIR}/spdlog-prefix")
    # execute_process 里多个 COMMAND 是管道，不是先后执行。
    execute_process(
        COMMAND "${CMAKE_COMMAND}" -S "${spdlog_SOURCE_DIR}" -B "${_AURORA_SPDLOG_BUILD}"
            -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
            -DCMAKE_INSTALL_PREFIX=${_AURORA_SPDLOG_PREFIX}
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
            -DSPDLOG_BUILD_PIC=ON
            -DSPDLOG_FMT_EXTERNAL=OFF
            -DSPDLOG_BUILD_EXAMPLE=OFF
            -DSPDLOG_BUILD_TESTS=OFF
            -DSPDLOG_BUILD_BENCH=OFF
        COMMAND_ERROR_IS_FATAL ANY
    )
    execute_process(
        COMMAND "${CMAKE_COMMAND}" --build "${_AURORA_SPDLOG_BUILD}" --parallel
        COMMAND_ERROR_IS_FATAL ANY
    )
    execute_process(
        COMMAND "${CMAKE_COMMAND}" --install "${_AURORA_SPDLOG_BUILD}"
        COMMAND_ERROR_IS_FATAL ANY
    )
    unset(spdlog_DIR CACHE)
    list(PREPEND CMAKE_PREFIX_PATH "${_AURORA_SPDLOG_PREFIX}")
    find_package(spdlog 1.15 REQUIRED)

    install(CODE "
        execute_process(
            COMMAND \"${CMAKE_COMMAND}\" --install \"${_AURORA_SPDLOG_BUILD}\"
                    --prefix \"\${CMAKE_INSTALL_PREFIX}\"
            COMMAND_ERROR_IS_FATAL ANY
        )
    ")
else()
    message(STATUS "Using spdlog >= 1.15: ${spdlog_DIR}")
endif()

# ── library ───────────────────────────────────────────────────────────────────

add_library(aurora_logger STATIC
    src/logger.cpp
)
add_library(aurora::aurora_logger ALIAS aurora_logger)

set_target_properties(aurora_logger PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    OUTPUT_NAME aurora_logger
    VERSION ${PROJECT_VERSION}
)

target_include_directories(aurora_logger PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/aurora>
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

# ── install ───────────────────────────────────────────────────────────────────

install(TARGETS aurora_logger
    EXPORT aurora_loggerTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/aurora
)

install(FILES
    src/log.hpp
    src/logger.hpp
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/aurora
)

install(EXPORT aurora_loggerTargets
    FILE aurora_loggerTargets.cmake
    NAMESPACE aurora::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aurora_logger
)

configure_package_config_file(
    cmake/aurora_loggerConfig.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/aurora_loggerConfig.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aurora_logger
)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/aurora_loggerConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/aurora_loggerConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/aurora_loggerConfigVersion.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aurora_logger
)
