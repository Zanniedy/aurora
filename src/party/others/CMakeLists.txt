# 第三方小库，保留原有实现以减少迁移风险。
# 只有 liblzf 有源文件，其余都是头文件。
add_library(aurora_party_others INTERFACE)
add_library(aurora::party_others ALIAS aurora_party_others)
target_include_directories(aurora_party_others SYSTEM INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})

add_library(aurora_lzf STATIC liblzf/lzf_c.c liblzf/lzf_d.c)
set_target_properties(aurora_lzf PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(aurora_lzf PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
