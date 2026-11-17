#!/usr/bin/env bash
# Download the model files used in the study and verify their SHA-256 checksums.
# Usage: scripts/fetch_model.sh m3_distilbert
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL=${1:?model id}
case "$MODEL" in
  m3_distilbert)
    BASE="https://huggingface.co/Xenova/distilbert-base-uncased-finetuned-sst-2-english/resolve/main"
    FILES=("onnx/model_quantized.onnx|model.onnx|79b45c7fd8c2673aa53615aba07caeb2de798f63a95a2393a365982429c94f7f"
           "tokenizer.json|tokenizer.json|d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"
           "config.json|config.json|b0e9ec981125ef799f31847b1410053069e7708078bb2236ae05239efdd4d428") ;;
  *) echo "unknown model $MODEL" >&2; exit 1 ;;
esac

mkdir -p "models/$MODEL"
for entry in "${FILES[@]}"; do
  IFS='|' read -r src dst sha <<< "$entry"
  out="models/$MODEL/$dst"
  [ -f "$out" ] || curl -sSfL -o "$out" "$BASE/$src"
  echo "$sha  $out" | shasum -a 256 -c -
done
