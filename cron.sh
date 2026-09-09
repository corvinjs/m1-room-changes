#!/bin/bash
# Install / remove / run the calendar snapshot cron for GitHub Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MARKER="# m1-room-changes"
LINE="17 */4 * * * $ROOT/cron.sh run >>$ROOT/cron.log 2>&1"
LOCK="$ROOT/.lock"
SITE_ROOT="${M1_SITE_ROOT:-/mnt/win/Code/corvin.sydow.ch}"
ICS_URL="https://calendar.google.com/calendar/ical/masterm1physique%40gmail.com/public/basic.ics"

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
  cd "$ROOT"

  ICS_TMP="$(mktemp)"
  HTML_TMP="$(mktemp)"
  trap 'rm -f "$ICS_TMP" "$HTML_TMP"' EXIT

  /usr/bin/curl --fail --silent --show-error --location \
    --connect-timeout 10 --max-time 60 "$ICS_URL" -o "$ICS_TMP"
  test -s "$ICS_TMP"

  test -d "$SITE_ROOT/.git"
  /usr/bin/python3 "$ROOT/build_static_site.py" "$ICS_TMP" "$HTML_TMP" \
    --canonical-ics "$ICS_TMP"
  if /usr/bin/python3 "$ROOT/build_static_site.py" "$ICS_TMP" \
    --data-unchanged --compare-with "$ROOT/index.html" --candidate "$HTML_TMP"; then
    echo "calendar data unchanged"
  else
    /usr/bin/install -m 0644 "$HTML_TMP" "$ROOT/index.html"
    (
      cd "$ROOT"
      git add index.html
      git commit -m "Update calendar snapshot"
    )
  fi

  CHILD_AHEAD="$(
    cd "$ROOT"
    git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0
  )"
  PARENT_AHEAD="$(
    cd "$SITE_ROOT"
    git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0
  )"
  if [ "$CHILD_AHEAD" -gt 0 ] || [ "$PARENT_AHEAD" -gt 0 ]; then
    echo "calendar push incomplete; retrying on the next run" >&2
    exit 1
  fi
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
