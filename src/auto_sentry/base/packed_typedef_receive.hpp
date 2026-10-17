#pragma once
#include <cstdint>

#include <atomic>
#include <cstring>
#include <optional>
#include  <vector>

namespace aurora::data::receive {
        struct ReceiveRobotData {
            static constexpr uint8_t ID = 0x02 ;   //命令控制码 

            uint8_t cmd_ID ;
            uint32_t time_stamp_pc  ;              //收到的上一个包的时间戳 具体的定义来源官方的通讯文件 
            uint32_t time_stamp_receive_micro ;    //收到上一个stm32的时间戳
            uint32_t time_stamp_sent_micro ;        //发送次包的时间戳

            float yaw , pitch , roll ;
            float  vyaw , vpitch  , vroll ; 

            float v_x ,v_y ,v_z ;

            float bullet_speed ; 
            uint8_t detect_color ;
            uint32_t bullet_count ;

            float operator_yaw_offset ;
            float operator_pitch_offset ;

            static std::optional<ReceiveRobotData> create (const std::vector<uint8_t> data) {
                if (data.size() != sizeof(ReceiveRobotData) || data[0] != ID) 
                return std::nullopt;

            ReceiveRobotData out ;
            std::memcpy(&out, data.data() , sizeof(out)) ;
            return out;

            //基本的发送消息的接口用来和下位机通讯
            } 
        } data_receive 

        struct SentryRefereeReceive{}

} //namespace aurora::data::receive