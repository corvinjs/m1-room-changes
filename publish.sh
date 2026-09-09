#!/bin/bash
# Force a rebuild and publish of the static calendar site.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ICS_URL="https://calendar.google.com/calendar/ical/masterm1physique%40gmail.com/public/basic.ics"
ICS_TMP="$(mktemp)"
trap 'rm -f "$ICS_TMP"' EXIT

/usr/bin/curl --fail --silent --show-error --location \
  --connect-timeout 10 --max-time 60 "$ICS_URL" -o "$ICS_TMP"
test -s "$ICS_TMP"

/usr/bin/python3 "$ROOT/build_static_site.py" "$ICS_TMP" "$ROOT/index.html"

(
  cd "$ROOT"
  git add index.html
  git commit -m "Publish calendar snapshot"
)
