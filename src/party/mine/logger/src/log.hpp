#pragma once

#ifndef SPDLOG_ACTIVE_LEVEL
#define SPDLOG_ACTIVE_LEVEL SPDLOG_LEVEL_TRACE
#endif

#include "logger.hpp"

#define AURORA_TRACE(...)    SPDLOG_LOGGER_TRACE(::aurora::logger::get_logger(), __VA_ARGS__)
#define AURORA_DEBUG(...)    SPDLOG_LOGGER_DEBUG(::aurora::logger::get_logger(), __VA_ARGS__)
#define AURORA_INFO(...)     SPDLOG_LOGGER_INFO(::aurora::logger::get_logger(), __VA_ARGS__)
#define AURORA_WARN(...)     SPDLOG_LOGGER_WARN(::aurora::logger::get_logger(), __VA_ARGS__)
#define AURORA_ERROR(...)    SPDLOG_LOGGER_ERROR(::aurora::logger::get_logger(), __VA_ARGS__)
#define AURORA_CRITICAL(...) SPDLOG_LOGGER_CRITICAL(::aurora::logger::get_logger(), __VA_ARGS__)
