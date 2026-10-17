#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-sentry}"
ACTION="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="${AURORA_SERVICE_NAME:-aurora-auto-aim-${PROFILE}}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONFIG_PATH="${AURORA_CONFIG:-$WORK_DIR/config/sentry.yaml}"
DEBUG="${AURORA_DEBUG:-false}"

if [[ "$CONFIG_PATH" != /* ]]; then
    CONFIG_PATH="$WORK_DIR/$CONFIG_PATH"
fi

if [[ -z "$ACTION" ]]; then
    echo "Usage: $0 <profile> [install|uninstall|start|stop|restart|status|journal]"
    exit 2
fi

uninstall_service() {
    sudo systemctl disable --now "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo rm -f "$SERVICE_FILE"
    sudo systemctl daemon-reload
    echo "Removed ${SERVICE_NAME}.service"
}

install_service() {
    if [[ ! -x "$WORK_DIR/run.sh" ]]; then
        echo "run.sh not found: $WORK_DIR/run.sh" >&2
        exit 1
    fi
    if [[ ! -f "$CONFIG_PATH" ]]; then
        echo "config not found: $CONFIG_PATH" >&2
        exit 1
    fi

    sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Aurora auto-aim (${PROFILE})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${WORK_DIR}
Environment=AURORA_ROOT=${WORK_DIR}
Environment=VISION_ROOT=${WORK_DIR}
ExecStart=${WORK_DIR}/run.sh run auto_aim ${CONFIG_PATH} ${DEBUG}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo chmod 644 "$SERVICE_FILE"
    sudo systemctl daemon-reload
    sudo systemctl enable --now "${SERVICE_NAME}.service"
    echo "Installed and started ${SERVICE_NAME}.service"
}

case "$ACTION" in
    install) install_service ;;
    uninstall) uninstall_service ;;
    start) sudo systemctl start "${SERVICE_NAME}.service" ;;
    stop) sudo systemctl stop "${SERVICE_NAME}.service" ;;
    restart) sudo systemctl restart "${SERVICE_NAME}.service" ;;
    status) sudo systemctl status "${SERVICE_NAME}.service" ;;
    journal) sudo journalctl -u "${SERVICE_NAME}.service" --no-pager ;;
    *)
        echo "Unknown action: $ACTION" >&2
        exit 2
        ;;
esac
