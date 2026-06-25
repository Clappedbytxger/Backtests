#!/usr/bin/env bash
#
# Populate the Tauri resources/ folder with the data the desktop app ships:
#   * strategies.db            (the registry → dashboard table + strategy detail pages)
#   * strategies/*/results/*.png  (the plots shown on each strategy detail page)
#
# Run on the Mac (or anywhere with the repo data present) BEFORE `npm run desktop:build`.
# Tauri bundles resources/ into the .app; the sidecar seeds it into a writable dir on the
# first launch, so the shipped .dmg starts self-contained with data.
#
#     bash scripts/bundle_data.sh

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root
ROOT="$(pwd)"
RES="$ROOT/apps/web/src-tauri/resources"

echo "==> populating $RES"
rm -rf "$RES/strategies" "$RES/strategies.db"
mkdir -p "$RES"

if [ -f "$ROOT/strategies.db" ]; then
  cp "$ROOT/strategies.db" "$RES/strategies.db"
  echo "    + strategies.db ($(du -h "$RES/strategies.db" | cut -f1))"
else
  echo "    ! strategies.db missing — build it first:"
  echo "        .venv/bin/python scripts/build_registry.py"
fi

count=0
while IFS= read -r d; do
  destdir="$RES/$d"
  mkdir -p "$destdir"
  for png in "$ROOT/$d"/*.png; do
    [ -e "$png" ] || continue
    cp "$png" "$destdir/"
    count=$((count + 1))
  done
done < <(cd "$ROOT" && find strategies -type d -name results)

echo "==> bundled $count result plots"
echo "==> done — now build: cd apps/web && npm run desktop:build"
