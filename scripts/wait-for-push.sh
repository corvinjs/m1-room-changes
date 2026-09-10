#!/bin/bash
# Retry git push until the branch is no longer ahead of its upstream.
set -euo pipefail

DIR="$1"
RETRIES="${2:-5}"
SLEEP="${3:-2}"

for _ in $(seq 1 "$RETRIES"); do
  AHEAD="$(cd "$DIR" && git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
  if [ "$AHEAD" -eq 0 ]; then
    exit 0
  fi
  sleep "$SLEEP"
  (cd "$DIR" && git push --quiet) || true
done

AHEAD="$(cd "$DIR" && git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
if [ "$AHEAD" -gt 0 ]; then
  echo "push incomplete in $DIR ($AHEAD commit(s) ahead)" >&2
  exit 1
fi
