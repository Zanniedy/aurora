# 哨兵上层：base（串口协议、公共类型）、aim（自瞄）、buff（能量机关）、
# brain（决策）和 radar（雷达站，可选）。

find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(TBB REQUIRED)
find_package(Ceres REQUIRED)

add_library(aurora_auto_sentry INTERFACE)
add_library(aurora::auto_sentry ALIAS aurora_auto_sentry)
target_include_directories(aurora_auto_sentry INTERFACE
    ${AURORA_SRC_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# 决策目前全是头文件。
add_library(aurora_brain INTERFACE)
add_library(aurora::brain ALIAS aurora_brain)
target_link_libraries(aurora_brain INTERFACE aurora::rcl aurora::auto_sentry)

add_library(aurora_mpc STATIC
    ${AURORA_SRC_DIR}/party/others/tinympc/tiny_api.cpp
    ${AURORA_SRC_DIR}/party/others/tinympc/admm.cpp
    ${AURORA_SRC_DIR}/party/others/tinympc/rho_benchmark.cpp
)
add_library(aurora::mpc ALIAS aurora_mpc)
target_include_directories(aurora_mpc PUBLIC
    ${AURORA_SRC_DIR}/party/others
)
target_link_libraries(aurora_mpc PUBLIC Eigen3::Eigen)

file(GLOB_RECURSE AURORA_AUTO_AIM_SOURCES CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/aim/*.cpp
)
list(FILTER AURORA_AUTO_AIM_SOURCES EXCLUDE REGEX "/experimental/")
add_library(aurora_auto_aim STATIC ${AURORA_AUTO_AIM_SOURCES})
add_library(aurora::auto_aim ALIAS aurora_auto_aim)
target_include_directories(aurora_auto_aim PUBLIC
    ${AURORA_SRC_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${AURORA_GENERATED_DIR}
)
target_link_libraries(aurora_auto_aim PUBLIC
    aurora::utils
    aurora::party_others
    aurora::mpc
    Eigen3::Eigen
    ${OpenCV_LIBS}
    yaml-cpp
    TBB::tbb
    Ceres::ceres
)

if(AURORA_WITH_OPENVINO)
    target_compile_definitions(aurora_auto_aim PUBLIC USE_OPENVINO)
endif()

if(AURORA_WITH_TRT)
    target_sources(aurora_auto_aim PRIVATE
        ${AURORA_SRC_DIR}/utils/net_detector/tensorrt/net_detector_tensorrt.cpp
        ${AURORA_SRC_DIR}/utils/cuda/letter_box.cu
        ${AURORA_SRC_DIR}/utils/cuda/cvtcolor.cu
    )
    target_link_libraries(aurora_auto_aim PUBLIC aurora_trt)
endif()

file(GLOB_RECURSE AURORA_AUTO_BUFF_SOURCES CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/buff/*.cpp
)
add_library(aurora_auto_buff STATIC ${AURORA_AUTO_BUFF_SOURCES})
add_library(aurora::auto_buff ALIAS aurora_auto_buff)
target_include_directories(aurora_auto_buff PUBLIC
    ${AURORA_SRC_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${AURORA_GENERATED_DIR}
)
target_link_libraries(aurora_auto_buff PUBLIC
    aurora::auto_aim
    aurora::utils
    aurora::party_others
    aurora::mpc
    Eigen3::Eigen
    ${OpenCV_LIBS}
    yaml-cpp
    TBB::tbb
    Ceres::ceres
)

if(AURORA_WITH_OPENVINO)
    target_compile_definitions(aurora_auto_buff PUBLIC USE_OPENVINO)
endif()

if(AURORA_BUILD_RADAR)
    find_package(Open3D REQUIRED)

    # 不依赖推理后端的部分：裁判系统收发、livox v1 驱动、定位、跟踪。
    add_library(aurora_radar STATIC
        radar/io/crc.cpp
        radar/livox_v1/livox_v1_publisher.cpp
        radar/lidar_location.cpp
    )
    add_library(aurora::radar ALIAS aurora_radar)
    target_link_libraries(aurora_radar PUBLIC aurora::rcl aurora::auto_sentry Open3D::Open3D)

    if(AURORA_WITH_TRT)
        add_library(aurora_radar_detect STATIC
            radar/detector.cpp
            ${AURORA_SRC_DIR}/utils/net_detector/tensorrt/net_detector_tensorrt.cpp
            ${AURORA_SRC_DIR}/utils/cuda/letter_box.cu
            ${AURORA_SRC_DIR}/utils/cuda/cvtcolor.cu
        )
        target_link_libraries(aurora_radar_detect PUBLIC aurora::radar aurora_trt)
    endif()
endif()
