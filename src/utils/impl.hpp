#pragma once
#include <memory>
namespace aurora {}
#define AURORA_IMPL_DEFINITION(CLASS) \
public: \
    ~CLASS() noexcept; \
\
private: \
    struct Impl; \
    std::unique_ptr<Impl> _impl; \
\
public:
