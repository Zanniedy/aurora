# 通用基础设施：类型、tf、调度器、串口、相机、pcd 读写。
find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(TBB REQUIRED)
find_package(Ceres REQUIRED)
find_package(Boost REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(HikSDK QUIET)
find_package(MvSDK QUIET)
find_package(DahengSDK QUIET)

# 导航也要用 pcd 读写，但不需要其余 utils，单独成库。
add_library(aurora_pcd_io STATIC io/pcd_io.cpp)
set_target_properties(aurora_pcd_io PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(aurora_pcd_io PUBLIC ${AURORA_SRC_DIR})
target_link_libraries(aurora_pcd_io PUBLIC aurora_lzf Eigen3::Eigen)

add_library(aurora_utils STATIC
    drivers/camera_factory.cpp
    drivers/hik_camera.cpp
    drivers/mv_camera.cpp
    drivers/daheng_camera.cpp
)
add_library(aurora::utils ALIAS aurora_utils)
set_target_properties(aurora_utils PROPERTIES POSITION_INDEPENDENT_CODE ON)

target_include_directories(aurora_utils PUBLIC
    ${AURORA_SRC_DIR}
    ${AURORA_GENERATED_DIR}
)
target_link_libraries(aurora_utils PUBLIC
    aurora::aurora_logger
    aurora::party_others
    aurora_pcd_io
    Eigen3::Eigen
    ${OpenCV_LIBS}
    yaml-cpp
    TBB::tbb
    Ceres::ceres
    Boost::boost
    nlohmann_json::nlohmann_json
)

find_library(AURORA_SYSTEM_CURL NAMES curl
    PATHS /usr/lib/x86_64-linux-gnu /usr/lib64 /usr/lib
    NO_DEFAULT_PATH)
if(AURORA_SYSTEM_CURL)
    target_link_libraries(aurora_utils PUBLIC ${AURORA_SYSTEM_CURL})
endif()

foreach(_sdk HikSDK MvSDK DahengSDK)
    if(${_sdk}_FOUND)
        target_compile_definitions(aurora_utils PUBLIC USE_${_sdk})
        target_link_libraries(aurora_utils PUBLIC ${_sdk}::${_sdk})
    endif()
endforeach()

if(AURORA_WITH_OPENVINO)
    target_sources(aurora_utils PRIVATE
        net_detector/openvino/net_detector_openvino.cpp
    )
    target_compile_definitions(aurora_utils PUBLIC USE_OPENVINO)
    target_link_libraries(aurora_utils PUBLIC
        openvino::runtime
        openvino::frontend::onnx
    )
endif()
