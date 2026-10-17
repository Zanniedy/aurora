#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
MARKER_START="# >>> aurora dev >>>"
MARKER_END="# <<< aurora dev <<<"
BACKUP="$BASHRC.bak.$(date +%Y%m%d_%H%M%S)"

# 备份
cp "$BASHRC" "$BACKUP"
echo "💾 已备份 $BASHRC 到 $BACKUP"

# 临时文件
TMP=$(mktemp)

# 写入 bashrc 除去旧 block
awk -v start="$MARKER_START" -v end="$MARKER_END" '
  $0 == start {inside=1; next}
  inside && $0 == end {inside=0; next}
  !inside {print}
' "$BASHRC" > "$TMP"

# 使用 cat <<EOF 方式追加 block，保证特殊字符安全
cat <<'EOF' >> "$TMP"
# >>> aurora dev >>>
py() { 
    if [ -f "${CONDA_EXE:-}/../etc/profile.d/conda.sh" ]; then
        source "${CONDA_EXE}/../etc/profile.d/conda.sh"
    fi
    echo "已激活 conda, conda activate激活环境，conda deactivate退出环境， conda info --envs查看环境"
}

buildme() {
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel
}

builddebug() {
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build --parallel
}

killros() { 
    pkill -f ros && ros2 daemon stop && ros2 daemon start
}

format() { 
    find . -path ./build -prune -o \
    -type f \( -name '*.h' -o -name '*.hpp' -o -name '*.c' -o -name '*.cu' -o -name '*.cpp' \) \
    -exec clang-format -i {} +
}

s() {
    export AURORA_ROOT="$PWD"
}

hik() { 
    export MVCAM_SDK_PATH=/opt/MVS
    export MVCAM_COMMON_RUNENV=/opt/MVS/lib
    export MVCAM_GENICAM_CLPROTOCOL=/opt/MVS/lib/CLProtocol
    export ALLUSERSPROFILE=/opt/MVS/MVFG
    export LD_LIBRARY_PATH=/opt/MVS/lib/64:/opt/MVS/lib/32:$LD_LIBRARY_PATH
}
# <<< aurora dev <<<
EOF

# 原子替换
mv "$TMP" "$BASHRC"
echo "✅ 已安全替换或追加 block 到 $BASHRC"
