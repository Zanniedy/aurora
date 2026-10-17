#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$(dirname "$SCRIPT_DIR")"
echo "脚本目录: $SCRIPT_DIR"
echo "aurora目录: $WORK_DIR"
# 用法说明
if [ $# -lt 2 ] || [ $# -gt 3 ]; then
    echo "Usage: $0 <remote_user> <remote_ip> [remote_project_dir]"
    echo "Example:"
    echo "  $0 nvidiaa 192.168.10.100"
    exit 1
fi


REMOTE_USER="$1"
REMOTE_IP="$2"
REMOTE_PROJECT_DIR="${3:-aurora}"
TARGET_PATH="/home/${REMOTE_USER}/${REMOTE_PROJECT_DIR}"
rsync -avz \
    --exclude='.cache/' \
    --exclude='.vscode/' \
    --exclude='.git/' \
    --exclude='bin/' \
    --exclude='build/' \
    --exclude='log/' \
    --exclude='record/' \
    --exclude='.codex' \
    --exclude='.agents' \
    "${WORK_DIR}/" \
    "${REMOTE_USER}@${REMOTE_IP}:${TARGET_PATH}/"
