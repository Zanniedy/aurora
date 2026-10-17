# 可执行入口。产物统一放 build/bin，launch 文件按这个路径找。

function(aurora_add_executable name)
    add_executable(${name} ${ARGN})
    set_target_properties(${name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${AURORA_BIN_DIR})
endfunction()

# 导航三进程
aurora_add_executable(nav_lm nav_lm.cpp)
aurora_add_executable(nav_map nav_map.cpp)
aurora_add_executable(nav_planner nav_planner.cpp)
foreach(_t nav_lm nav_map nav_planner)
    target_link_libraries(${_t} PRIVATE aurora::nav)
endforeach()

# 串口 + 决策 + cmd_vel 转发。
aurora_add_executable(sentry_nav sentry_nav.cpp)
target_link_libraries(sentry_nav PRIVATE aurora::brain)

aurora_add_executable(auto_aim_probe auto_aim_probe.cpp)
target_link_libraries(auto_aim_probe PRIVATE aurora::auto_aim)

aurora_add_executable(auto_aim auto_aim.cpp)
target_link_libraries(auto_aim PRIVATE
    aurora::auto_aim
    aurora::auto_buff
    aurora::utils
    aurora::party_others
)
find_library(AURORA_SYSTEM_CURL NAMES curl
    PATHS /usr/lib/x86_64-linux-gnu /usr/lib64 /usr/lib
    NO_DEFAULT_PATH)
if(AURORA_SYSTEM_CURL)
    target_link_libraries(auto_aim PRIVATE ${AURORA_SYSTEM_CURL})
endif()

aurora_add_executable(map_edit map_edit.cpp)
target_link_libraries(map_edit PRIVATE aurora::brain)

if(AURORA_BUILD_RADAR)
    aurora_add_executable(livox_v1_driver livox_v1_driver.cpp)
    target_link_libraries(livox_v1_driver PRIVATE aurora::radar)
    aurora_add_executable(radar_cal radar_cal.cpp)
    target_link_libraries(radar_cal PRIVATE aurora::radar)
    if(AURORA_WITH_TRT)
        aurora_add_executable(radar_detect radar_detect.cpp)
        target_link_libraries(radar_detect PRIVATE aurora_radar_detect)
    endif()
endif()
