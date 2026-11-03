#!/bin/bash
# Run the calendar snapshot update for GitHub Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOCK="$ROOT/.lock"
SITE_ROOT="${M1_SITE_ROOT:-/mnt/win/Code/corvin.sydow.ch}"

exec 9>"$LOCK"
flock -n 9 || exit 0

test -d "$SITE_ROOT/.git"
"$ROOT/scripts/update-site.sh"

bash "$ROOT/scripts/wait-for-push.sh" "$ROOT"
bash "$ROOT/scripts/wait-for-push.sh" "$SITE_ROOT"
