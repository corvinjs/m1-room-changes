#!/bin/bash
# Install or remove the user systemd timer for the calendar snapshot.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="$UNIT_DIR/m1-room-changes.service"
TIMER="$UNIT_DIR/m1-room-changes.timer"
SITE_ROOT="${M1_SITE_ROOT:-/mnt/win/Code/corvin.sydow.ch}"

install() {
  mkdir -p "$UNIT_DIR"
  sed -e "s|@ROOT@|$ROOT|g" -e "s|@SITE_ROOT@|$SITE_ROOT|g" \
    "$ROOT/systemd/m1-room-changes.service.in" >"$SERVICE"
  cp "$ROOT/systemd/m1-room-changes.timer" "$TIMER"
  systemctl --user daemon-reload
  systemctl --user enable --now m1-room-changes.timer
  echo "installed: m1-room-changes.timer"
}

remove() {
  systemctl --user disable --now m1-room-changes.timer 2>/dev/null || true
  rm -f "$SERVICE" "$TIMER"
  systemctl --user daemon-reload
  echo "removed: m1-room-changes.timer"
}

case "${1:-}" in
  install) install ;;
  remove) remove ;;
  *)
    echo "usage: $0 install|remove" >&2
    exit 2
    ;;
esac
