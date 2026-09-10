#!/bin/bash
# Force a rebuild and publish of the static calendar site.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/scripts/update-site.sh" --force
