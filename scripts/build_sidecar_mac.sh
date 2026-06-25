#!/usr/bin/env bash
#
# Build the Quant-OS API as a standalone Apple-Silicon sidecar binary for the Tauri app.
# Run this ON THE MAC, inside the project's Python venv, from anywhere in the repo:
#
#     source .venv/bin/activate          # the Mac venv (see DESKTOP_BUILD.md)
#     bash scripts/build_sidecar_mac.sh
#
# Output: apps/web/src-tauri/binaries/quant-os-api-aarch64-apple-darwin
# (this exact name is what Tauri's `externalBin` expects for the arm64 target).
#
# The binary is large (pandas/scipy/scikit-learn/lightgbm get bundled). Torch and the
# LLM-inference backends are intentionally excluded (the agent routes don't work frozen
# anyway). If freezing fails on a missing module, adjust the --collect/--exclude flags.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root
ROOT="$(pwd)"
TRIPLE="aarch64-apple-darwin"
NAME="quant-os-api"
OUT_DIR="$ROOT/apps/web/src-tauri/binaries"

echo "==> repo root : $ROOT"
echo "==> python    : $(command -v python)"
echo "==> installing pyinstaller (no-op if present)…"
pip install --quiet pyinstaller

echo "==> freezing the API (this takes a few minutes)…"
pyinstaller \
  --noconfirm --clean --onefile \
  --name "$NAME" \
  --distpath "$ROOT/build/sidecar/dist" \
  --workpath "$ROOT/build/sidecar/work" \
  --specpath "$ROOT/build/sidecar" \
  --paths "$ROOT/src" --paths "$ROOT" \
  --collect-submodules quantlab \
  --collect-submodules apps \
  --collect-all fastapi --collect-all starlette --collect-all uvicorn \
  --collect-all pydantic --collect-all pydantic_settings \
  --collect-all pandas --collect-all numpy \
  --collect-all scipy --collect-all sklearn --collect-all lightgbm \
  --collect-all yfinance --collect-all yaml \
  --hidden-import apps.api.main \
  --exclude-module torch --exclude-module torchvision \
  --exclude-module transformers --exclude-module llama_cpp \
  --exclude-module mlx --exclude-module mlx_lm \
  "$ROOT/apps/api/sidecar_entry.py"

mkdir -p "$OUT_DIR"
cp "$ROOT/build/sidecar/dist/$NAME" "$OUT_DIR/$NAME-$TRIPLE"
chmod +x "$OUT_DIR/$NAME-$TRIPLE"

echo ""
echo "==> ✅ sidecar built:"
echo "    $OUT_DIR/$NAME-$TRIPLE"
echo ""
echo "    Quick self-test (Ctrl-C to stop, then open http://127.0.0.1:8000/health):"
echo "    \"$OUT_DIR/$NAME-$TRIPLE\""
