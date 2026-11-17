#!/usr/bin/env bash
# Build a Lambda zip package for one model and one architecture.
# Usage: scripts/build_zip.sh <model_id> <x86_64|arm64>
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL=${1:?model id, e.g. m3_distilbert}
ARCH=${2:?x86_64 or arm64}
case "$ARCH" in
  x86_64) PLAT=(--platform manylinux2014_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_28_x86_64) ;;
  arm64)  PLAT=(--platform manylinux2014_aarch64 --platform manylinux_2_27_aarch64 --platform manylinux_2_28_aarch64) ;;
  *) echo "unknown arch $ARCH" >&2; exit 1 ;;
esac

OUT="build/${MODEL}-${ARCH}"
rm -rf "$OUT"
mkdir -p "$OUT/pkg/model"

.venv/bin/pip install --quiet --no-deps --target "$OUT/pkg" "${PLAT[@]}" \
  --implementation cp --python-version 3.12 --only-binary=:all: -r requirements-lambda.txt

cp src/handler.py "$OUT/pkg/"
cp "models/$MODEL/model.onnx" "models/$MODEL/tokenizer.json" "$OUT/pkg/model/"
find "$OUT/pkg" -name __pycache__ -type d -prune -exec rm -rf {} +

(cd "$OUT/pkg" && zip -qr9X "../${MODEL}-${ARCH}.zip" .)

UNZIPPED=$(du -sk "$OUT/pkg" | cut -f1)
echo "package: $OUT/${MODEL}-${ARCH}.zip"
echo "unzipped_kb: $UNZIPPED (limit 256000)"
ls -l "$OUT/${MODEL}-${ARCH}.zip"
shasum -a 256 "$OUT/${MODEL}-${ARCH}.zip"
if [ "$UNZIPPED" -ge 256000 ]; then echo "ERROR: package exceeds 250 MB unzipped" >&2; exit 1; fi
