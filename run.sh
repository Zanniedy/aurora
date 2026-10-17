#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$ROOT_DIR/build"
BIN_DIR="$BUILD_DIR/bin"
export AURORA_ROOT="$ROOT_DIR"
export VISION_ROOT="$ROOT_DIR"
export MVCAM_SDK_PATH="${MVCAM_SDK_PATH:-/opt/MVS}"
export MVCAM_COMMON_RUNENV="${MVCAM_COMMON_RUNENV:-/opt/MVS/lib}"
export LD_LIBRARY_PATH="/opt/MVS/lib/64:/opt/MVS/lib/32:$ROOT_DIR/lib:${LD_LIBRARY_PATH:-}"

configure_and_build() {
    cmake -S "$ROOT_DIR" -B "$BUILD_DIR" \
        -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}" \
        -DAURORA_BUILD_RADAR="${AURORA_BUILD_RADAR:-OFF}" \
        -DAURORA_WITH_OPENVINO="${AURORA_WITH_OPENVINO:-OFF}" \
        -DAURORA_WITH_TRT="${AURORA_WITH_TRT:-OFF}" \
        "$@"
    cmake --build "$BUILD_DIR" --parallel
}

if [[ $# -eq 0 || "$1" == "build" ]]; then
    shift || true
    configure_and_build "$@"
    exit 0
fi

if [[ "$1" == "rebuild" ]]; then
    shift
    rm -rf "$BUILD_DIR"
    configure_and_build "$@"
    exit 0
fi

if [[ "$1" != "run" && "$1" != "debug" ]]; then
    echo "usage: $0 [build|rebuild|run|debug] <target> [args...]" >&2
    exit 2
fi

MODE="$1"
shift
TARGET="${1:-}"
shift || true
if [[ -z "$TARGET" ]]; then
    echo "missing target; available binaries:" >&2
    find "$BIN_DIR" -maxdepth 1 -type f -executable -printf '  %f\n' 2>/dev/null || true
    exit 2
fi

if [[ ! -x "$BIN_DIR/$TARGET" ]]; then
    configure_and_build
fi

if [[ ! -x "$BIN_DIR/$TARGET" ]]; then
    echo "binary not found: $BIN_DIR/$TARGET" >&2
    exit 1
fi

if [[ "$MODE" == "debug" ]]; then
    exec gdb --args "$BIN_DIR/$TARGET" "$@"
fi
exec "$BIN_DIR/$TARGET" "$@"
