#!/usr/bin/env bash
# Usage: ./build.sh [BASEURL] [OUTDIR]   (the page has no absolute links, BASEURL is unused)
set -euo pipefail
cd "$(dirname "$0")"
out="${2:-_site}"
mkdir -p "$out"
cp index.html "$out/"
