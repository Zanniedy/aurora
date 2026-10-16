#pragma once

include "logger.hpp"`

namespace aurora::slam
{
    struct SlamConfig
    {
        std::string map_file;
        std::string log_dir;
        bool use_sim_time = false;
    };

    class AuroraSlam
    {
    public:
        AuroraSlam(){
            aura::logger::init("log", spdlog::level::debug);
            AURORA_INFO("AuroraSlam initialized");
        };
        ~AuroraSlam() = default;

        void run();



    protected:
        void publishVisualization();
    };
} // namespace aurora