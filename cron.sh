#!/bin/bash
# Install / remove / run the calendar snapshot cron for GitHub Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MARKER="# m1-room-changes"
LINE="17 */4 * * * $ROOT/cron.sh run >>$ROOT/cron.log 2>&1"
LOCK="$ROOT/.lock"
SITE_ROOT="${M1_SITE_ROOT:-/mnt/win/Code/corvin.sydow.ch}"

install() {
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "m1-room-changes/cron.sh" >"$tmp" || true
  printf '%s\n%s\n' "$MARKER" "$LINE" >>"$tmp"
  crontab "$tmp"
  rm -f "$tmp"
  echo "installed: $LINE"
}

remove() {
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "m1-room-changes/cron.sh" >"$tmp" || true
  crontab "$tmp"
  rm -f "$tmp"
  echo "removed m1-room-changes cron line"
}

run() {
  exec 9>"$LOCK"
  flock -n 9 || exit 0

  test -d "$SITE_ROOT/.git"
  "$ROOT/scripts/update-site.sh"

  bash "$ROOT/scripts/wait-for-push.sh" "$ROOT"
  bash "$ROOT/scripts/wait-for-push.sh" "$SITE_ROOT"
}

case "${1:-}" in
  install) install ;;
  remove) remove ;;
  run) run ;;
  *)
    echo "usage: $0 install|remove|run" >&2
    exit 2
    ;;
esac
