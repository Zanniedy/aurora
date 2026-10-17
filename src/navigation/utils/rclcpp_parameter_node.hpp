#pragma once
#include "param_deliver.h"

#include <Eigen/Dense>
#include <rclcpp/node.hpp>
#include <cstdlib>
#include <string>
#include <type_traits>
namespace aurora::nav {
class ParamsNode {
public:
    ParamsNode(rclcpp::Node& node, std::string prefix = ""): node_(node) {
        if (!prefix.empty() && prefix.back() != '.')
            prefix += ".";
        prefix_ = std::move(prefix);
    }

    template<typename T>
    [[nodiscard]] T declare(const std::string& name, const T& default_value) const {
        const std::string full = prefix_ + name;

        if (node_.has_parameter(full)) {
            T value;
            node_.get_parameter(full, value);
            return expand(std::move(value));
        }

        return expand(node_.declare_parameter<T>(full, default_value));
    }
    template<typename T>
    [[nodiscard]] T declare(const std::string& name) const {
        const std::string full = prefix_ + name;

        if (node_.has_parameter(full)) {
            T value;
            node_.get_parameter(full, value);
            return expand(std::move(value));
        }

        return expand(node_.declare_parameter<T>(full));
    }

    [[nodiscard]] ParamsNode sub(const std::string& sub_prefix) const {
        return ParamsNode(node_, prefix_ + sub_prefix);
    }

private:
    template<typename T>
    static T expand(T value) {
        if constexpr (std::is_same_v<T, std::string>) {
            const char* root = std::getenv("AURORA_ROOT");
            const std::string root_dir = root ? root : ROOT_DIR;
            const std::string token = "${ROOT_DIR}";
            size_t pos = 0;
            while ((pos = value.find(token, pos)) != std::string::npos) {
                value.replace(pos, token.size(), root_dir);
                pos += root_dir.size();
            }
        }
        return value;
    }

    rclcpp::Node& node_;
    std::string prefix_;
};
} // namespace aurora::nav
