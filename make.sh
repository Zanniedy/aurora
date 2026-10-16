#!/bin/bash
# 用法: source ./make.sh [cmake 参数...]
# 必须用 source 执行，conda deactivate 才能生效到当前终端。
# 根目录是单体 CMake，不再走 colcon。

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "[error] 请用 'source ./make.sh' 执行，否则环境变量无法生效到当前终端"
    exit 1
fi

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_DIR"

if [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "[pre] Deactivating conda env: $CONDA_DEFAULT_ENV"
    CONDA_BASE="$(conda info --base 2>/dev/null)"
    if [ -n "$CONDA_BASE" ]; then
        # shellcheck disable=SC1091
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        conda deactivate
    fi
fi

if [ -z "${ROS_DISTRO:-}" ] && [ -f /opt/ros/humble/setup.bash ]; then
    echo "[pre] source /opt/ros/humble/setup.bash"
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
fi

echo "[1/2] Building..."
if ! cmake -S "$WORKSPACE_DIR" -B "$WORKSPACE_DIR/build" \
        -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        "$@"; then
    echo "[error] Configure failed."
    return 1
fi

if ! cmake --build "$WORKSPACE_DIR/build" --parallel; then
    echo "[error] Build failed."
    return 1
fi

echo "[2/2] Linking compile_commands.json..."
ln -sfn "$WORKSPACE_DIR/build/compile_commands.json" "$WORKSPACE_DIR/compile_commands.json"

echo ""
echo "Done."
echo "  clangd: Ctrl+Shift+P -> clangd: Restart language server"
