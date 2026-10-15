#!/usr/bin/env bash
# 通用构建，并生成 clangd 用的编译数据库。
#
# 覆盖三类后续代码，不用换入口：
#   - 根目录纯 CMake（当前这个日志库）
#   - 任意子目录里的 ROS 2 包（package.xml）
#   - third_party/ 下的第三方 CMake 库
#
# 用法:
#   ./make.sh                 配置、编译，合并 compile_commands.json
#   ./make.sh clean           删掉 build/ install/ compile_commands.json
#   ./make.sh rebuild         clean 之后重新编译
#   source ./make.sh          同上；若生成了 ROS overlay，则导入当前终端
#
# 可选参数:
#   --debug | --release       构建类型，默认 Release
#   --jobs N                  并行数，默认 nproc
#   --no-ros                  不 source /opt/ros
#   --prefix PATH             额外的库安装前缀，可重复
#   -D* / -W*                 传给 CMake
#   其余参数                  有 ROS 包时原样转给 colcon
#
# 环境变量:
#   CMAKE_PREFIX_PATH         已有的第三方前缀
#   ROS_DISTRO                默认 humble
#
# 产物:
#   ./compile_commands.json   合并后的 clangd 数据库。改完后执行
#                             Ctrl+Shift+P -> clangd: Restart language server

if [[ -n "${MAKE_SH_RUNNING:-}" ]]; then
    echo "[error] make.sh 不能嵌套执行" >&2
    return 1 2>/dev/null || exit 1
fi
export MAKE_SH_RUNNING=1

_MAKE_SH_SOURCED=0
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    _MAKE_SH_SOURCED=1
fi

_make_sh_finish() {
    local status=$1
    unset MAKE_SH_RUNNING
    if [[ "${_MAKE_SH_SOURCED}" -eq 1 ]]; then
        if [[ -n "${_MAKE_SH_OPTS:-}" ]]; then
            eval "${_MAKE_SH_OPTS}"
        fi
        return "${status}"
    fi
    exit "${status}"
}

_MAKE_SH_OPTS="$(set +o)"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

die() {
    echo "[error] $*" >&2
    exit 1
}

source_relaxed() {
    local file=$1
    set +u
    # shellcheck disable=SC1090
    source "${file}"
    set -u
}

prepare_env() {
    if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        echo "[env] 退出 conda: ${CONDA_DEFAULT_ENV}（避免它挡住系统库和 ROS）"
        local conda_base=""
        conda_base="$(conda info --base 2>/dev/null || true)"
        if [[ -n "${conda_base}" && -f "${conda_base}/etc/profile.d/conda.sh" ]]; then
            source_relaxed "${conda_base}/etc/profile.d/conda.sh"
            set +eu
            conda deactivate || true
            set -eu
        fi
    fi

    if [[ "${USE_ROS}" -eq 1 ]]; then
        local distro="${ROS_DISTRO:-humble}"
        local setup="/opt/ros/${distro}/setup.bash"
        if [[ -f "${setup}" ]]; then
            echo "[env] source ${setup}"
            source_relaxed "${setup}"
        else
            echo "[env] 未找到 ${setup}，跳过 ROS 环境"
        fi
    fi

    local prefix="${ROOT}/install/deps"
    local joined="${prefix}"
    local extra
    for extra in "${PREFIXES[@]}"; do
        joined="${extra}:${joined}"
    done
    if [[ -n "${CMAKE_PREFIX_PATH:-}" ]]; then
        joined="${joined}:${CMAKE_PREFIX_PATH}"
    fi
    CMAKE_PREFIX_PATH="${joined}"
    export CMAKE_PREFIX_PATH
}

run_clean() {
    echo "[clean] ${ROOT}/build ${ROOT}/install ${ROOT}/compile_commands.json"
    rm -rf "${ROOT}/build" "${ROOT}/install" "${ROOT}/compile_commands.json"
}

build_third_party() {
    local proj name build_dir
    shopt -s nullglob
    for proj in "${ROOT}/third_party"/*/; do
        [[ -f "${proj}/CMakeLists.txt" ]] || continue
        name="$(basename "${proj}")"
        build_dir="${ROOT}/build/third_party/${name}"
        echo "[third_party] ${name}"
        cmake -S "${proj}" -B "${build_dir}" \
            -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
            -DCMAKE_INSTALL_PREFIX="${ROOT}/install/deps" \
            -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
            -DCMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH}" \
            "${CMAKE_ARGS[@]}"
        cmake --build "${build_dir}" --parallel "${JOBS}"
        cmake --install "${build_dir}"
    done
    shopt -u nullglob
}

discover_ros_packages() {
    ROS_PACKAGES=()
    local manifest
    while IFS= read -r -d '' manifest; do
        ROS_PACKAGES+=("$(dirname "${manifest}")")
    done < <(find "${ROOT}" -name package.xml \
        -not -path '*/build/*' \
        -not -path '*/install/*' \
        -not -path '*/.git/*' \
        -not -path '*/third_party/*' \
        -not -path '*/_deps/*' \
        -not -path '*/log/*' \
        -print0)
}

build_cmake_project() {
    local build_dir=$1
    echo "[cmake] ${ROOT} -> ${build_dir}"
    local cmake_cmd=(
        cmake -S "${ROOT}" -B "${build_dir}"
        -DCMAKE_BUILD_TYPE="${BUILD_TYPE}"
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    )
    if [[ -n "${CMAKE_PREFIX_PATH}" ]]; then
        cmake_cmd+=(-DCMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH}")
    fi
    cmake_cmd+=("${CMAKE_ARGS[@]}")
    "${cmake_cmd[@]}"
    cmake --build "${build_dir}" --parallel "${JOBS}"
}

build_ros_packages() {
    local build_base=$1
    local install_base=$2
    command -v colcon >/dev/null 2>&1 || die "发现 ROS 包，但没有 colcon"
    echo "[ros2] colcon build (${#ROS_PACKAGES[@]} packages)"
    colcon build \
        --base-paths "${ROOT}" \
        --paths "${ROS_PACKAGES[@]}" \
        --build-base "${build_base}" \
        --install-base "${install_base}" \
        --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH}" -Wno-dev \
        "${COLCON_ARGS[@]}"
}

merge_compile_commands() {
    local db_files=()
    local found
    if [[ -d "${ROOT}/build" ]]; then
        while IFS= read -r -d '' found; do
            db_files+=("${found}")
        done < <(find "${ROOT}/build" -name compile_commands.json -print0)
    fi
    if [[ "${#db_files[@]}" -eq 0 ]]; then
        die "没有生成 compile_commands.json，clangd 仍然找不到头文件和源文件"
    fi

    echo "[clangd] 合并 ${#db_files[@]} 份 compile_commands.json"
    local tmp
    tmp="$(mktemp)"
    python3 - "${ROOT}" "${tmp}" "${db_files[@]}" << 'PY'
import json
import os
import shlex
import sys

workspace = os.path.realpath(sys.argv[1])
out_path = sys.argv[2]
db_files = sys.argv[3:]

def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []

def argv_of(entry):
    arguments = entry.get("arguments")
    if isinstance(arguments, list):
        return arguments
    command = entry.get("command")
    if isinstance(command, str) and command:
        return shlex.split(command)
    return []

def include_dirs(entry, directory):
    argv = argv_of(entry)
    index = 0
    while index < len(argv):
        arg = argv[index]
        path = None
        if arg in ("-I", "-isystem", "-iquote", "-idirafter") and index + 1 < len(argv):
            path = argv[index + 1]
            index += 2
        elif arg.startswith("-I") and len(arg) > 2:
            path = arg[2:]
            index += 1
        elif arg.startswith("-isystem") and len(arg) > 8:
            path = arg[8:]
            index += 1
        else:
            index += 1
            continue
        if not path or path.startswith("-"):
            continue
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(directory, path))
        yield os.path.realpath(path) if os.path.exists(path) else path

by_file = {}
missing_includes = []
for db in db_files:
    for entry in load(db):
        directory = os.path.realpath(entry.get("directory") or os.getcwd())
        source = entry.get("file") or ""
        if not os.path.isabs(source):
            source = os.path.join(directory, source)
        if not os.path.isfile(source):
            continue
        source = os.path.realpath(source)
        if "/_deps/" in source:
            continue
        entry["directory"] = directory
        entry["file"] = source
        for include in include_dirs(entry, directory):
            if include.startswith(workspace) and not os.path.isdir(include):
                missing_includes.append((source, include))
        by_file[source] = entry

entries = list(by_file.values())
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(entries, handle, indent=2)
    handle.write("\n")

seen = set()
for source, include in missing_includes:
    key = (source, include)
    if key in seen:
        continue
    seen.add(key)
    print(f"[warn] 头文件路径不存在: {include}\n       来自 {source}", file=sys.stderr)
PY
    local count
    count="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "${tmp}")"
    if [[ "${count}" -eq 0 ]]; then
        rm -f "${tmp}"
        die "合并后的编译数据库是空的"
    fi
    mv "${tmp}" "${ROOT}/compile_commands.json"
    chmod 644 "${ROOT}/compile_commands.json"

    local sources=()
    local source missing=0
    while IFS= read -r -d '' source; do
        sources+=("${source}")
    done < <(find "${ROOT}" \
        \( -path "${ROOT}/build" -o -path "${ROOT}/build/*" \
           -o -path "${ROOT}/install" -o -path "${ROOT}/install/*" \
           -o -path "${ROOT}/.git" -o -path "${ROOT}/.git/*" \
           -o -path "${ROOT}/third_party" -o -path "${ROOT}/third_party/*" \
           -o -path '*/_deps/*' -o -path "${ROOT}/log" -o -path "${ROOT}/log/*" \) -prune \
        -o \( -name '*.c' -o -name '*.cc' -o -name '*.cpp' -o -name '*.cxx' \) -print0)

    if [[ "${#sources[@]}" -gt 0 ]]; then
        local missing_list
        missing_list="$(python3 - "${ROOT}/compile_commands.json" "${sources[@]}" << 'PY'
import json
import os
import sys

database = {os.path.realpath(item["file"]) for item in json.load(open(sys.argv[1], encoding="utf-8"))}
for path in sys.argv[2:]:
    real = os.path.realpath(path)
    if real not in database:
        print(real)
PY
)"
        if [[ -n "${missing_list}" ]]; then
            missing=1
            while IFS= read -r source; do
                echo "[warn] clangd 数据库里没有这个源文件: ${source}" >&2
                echo "       把它加进对应的 CMakeLists.txt 或 ROS 包后再 ./make.sh" >&2
            done <<< "${missing_list}"
        fi
    fi

    echo "[clangd] ${ROOT}/compile_commands.json (${count} files)"
    if [[ "${missing}" -ne 0 ]]; then
        echo "[warn] 还有源文件没进编译数据库，clangd 会报找不到源文件" >&2
    fi
}

run_build() {
    build_third_party
    discover_ros_packages

    local has_cmake=0
    local root_is_ros=0
    [[ -f "${ROOT}/CMakeLists.txt" ]] && has_cmake=1
    [[ -f "${ROOT}/package.xml" ]] && root_is_ros=1

    if [[ "${has_cmake}" -eq 0 && "${#ROS_PACKAGES[@]}" -eq 0 ]]; then
        die "没找到 CMakeLists.txt 或 package.xml"
    fi

    local cmake_dir=""
    local colcon_build=""
    local colcon_install=""
    if [[ "${has_cmake}" -eq 1 && "${root_is_ros}" -eq 0 ]]; then
        if [[ "${#ROS_PACKAGES[@]}" -eq 0 ]]; then
            cmake_dir="${ROOT}/build"
        else
            cmake_dir="${ROOT}/build/cmake"
        fi
        build_cmake_project "${cmake_dir}"
    fi
    if [[ "${#ROS_PACKAGES[@]}" -gt 0 ]]; then
        if [[ -n "${cmake_dir}" ]]; then
            colcon_build="${ROOT}/build/colcon"
            colcon_install="${ROOT}/install"
        else
            colcon_build="${ROOT}/build"
            colcon_install="${ROOT}/install"
        fi
        build_ros_packages "${colcon_build}" "${colcon_install}"
    fi

    merge_compile_commands

    echo ""
    echo "Done."
    echo "  clangd: Ctrl+Shift+P -> clangd: Restart language server"
    if [[ -f "${ROOT}/install/setup.bash" && "${_MAKE_SH_SOURCED}" -eq 0 ]]; then
        echo "  ros2:   source ./make.sh    # 让当前终端用到 install/setup.bash"
    fi
}

BUILD_TYPE="Release"
JOBS="$(nproc)"
USE_ROS=1
PREFIXES=()
CMAKE_ARGS=()
COLCON_ARGS=()
COMMAND="build"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        build|clean|rebuild)
            COMMAND="$1"
            shift
            ;;
        --debug)
            BUILD_TYPE="Debug"
            shift
            ;;
        --release)
            BUILD_TYPE="Release"
            shift
            ;;
        --jobs)
            [[ "$#" -ge 2 ]] || die "--jobs 需要一个数字"
            JOBS="$2"
            shift 2
            ;;
        --no-ros)
            USE_ROS=0
            shift
            ;;
        --prefix)
            [[ "$#" -ge 2 ]] || die "--prefix 需要一个路径"
            PREFIXES+=("$2")
            shift 2
            ;;
        -h|--help)
            usage
            if [[ "${_MAKE_SH_SOURCED}" -eq 1 ]]; then
                return 0
            fi
            exit 0
            ;;
        -D*|-W*)
            CMAKE_ARGS+=("$1")
            shift
            ;;
        *)
            COLCON_ARGS+=("$1")
            shift
            ;;
    esac
done

# 环境改在当前 shell 里做：source ./make.sh 时 conda / ROS 才会留在这个终端。
# 编译放进子 shell，失败时 exit 不会把终端一起关掉。
if [[ "${COMMAND}" != "clean" ]]; then
    prepare_env
fi

set +e
(
    set -euo pipefail
    case "${COMMAND}" in
        clean)
            run_clean
            ;;
        rebuild)
            run_clean
            run_build
            ;;
        build)
            run_build
            ;;
        *)
            die "未知命令: ${COMMAND}"
            ;;
    esac
)
status=$?
set -e

if [[ "${status}" -eq 0 && "${_MAKE_SH_SOURCED}" -eq 1 && -f "${ROOT}/install/setup.bash" ]]; then
    echo "[env] source ${ROOT}/install/setup.bash"
    source_relaxed "${ROOT}/install/setup.bash"
fi

_make_sh_finish "${status}"
