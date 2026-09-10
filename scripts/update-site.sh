#!/bin/bash
# Fetch the ICS feed, build index.html, and optionally commit when data changed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORCE=false
COMMIT=true
COMMIT_MSG="Update calendar snapshot"

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      FORCE=true
      COMMIT_MSG="Publish calendar snapshot"
      ;;
    --no-commit) COMMIT=false ;;
    *)
      echo "usage: $0 [--force] [--no-commit]" >&2
      exit 2
      ;;
  esac
  shift
done

ICS_URL="$(/usr/bin/python3 -c "
import tomllib
from pathlib import Path
print(tomllib.loads(Path('$ROOT/settings.toml').read_text(encoding='utf-8'))['calendar_remote_id'])
")"

ICS_TMP="$(mktemp)"
HTML_TMP="$(mktemp)"
trap 'rm -f "$ICS_TMP" "$HTML_TMP"' EXIT

/usr/bin/curl --fail --silent --show-error --location \
  --connect-timeout 10 --max-time 60 "$ICS_URL" -o "$ICS_TMP"
test -s "$ICS_TMP"

/usr/bin/python3 "$ROOT/build_static_site.py" "$ICS_TMP" "$HTML_TMP"

if ! $FORCE && /usr/bin/python3 "$ROOT/build_static_site.py" "$ICS_TMP" \
  --data-unchanged --compare-with "$ROOT/index.html" --candidate "$HTML_TMP"; then
  echo "calendar data unchanged"
  exit 0
fi

/usr/bin/install -m 0644 "$HTML_TMP" "$ROOT/index.html"

if $COMMIT; then
  (
    cd "$ROOT"
    git add index.html
    git commit -m "$COMMIT_MSG"
  )
fi
