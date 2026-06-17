#!/usr/bin/env bash
# download-dilbert.sh — Download the DilBert v3 memory gate model
#
# Downloads the fine-tuned DistilBertForSequenceClassification model
# to ~/.remembrance/models/distilbert-memory-gate/
#
# The model is a 4-class classifier: SKIP / COLD / ACTIVE / PERSIST
# Base: distilbert-base-uncased | Accuracy: 90.1% | PERSIST recall: 0.91
#
# Usage:
#   bash scripts/download-dilbert.sh          # download to default location
#   bash scripts/download-dilbert.sh /path    # download to custom path

set -euo pipefail

DEFAULT_DIR="${HOME}/.remembrance/models/distilbert-memory-gate"
TARGET_DIR="${1:-$DEFAULT_DIR}"
RELEASE_TAG="v3.0-dilbert-gate"
REPO="emaharmony/rememberance-mcp"
BASE_URL="https://github.com/${REPO}/releases/download/${RELEASE_TAG}"

FILES=(
  "config.json"
  "tokenizer.json"
  "tokenizer_config.json"
  "model.safetensors"
)

echo "=== DilBert v3 Memory Gate — Model Download ==="
echo "Target: ${TARGET_DIR}"
echo ""

# Create target directory
mkdir -p "${TARGET_DIR}"

# Check if model already exists
if [ -f "${TARGET_DIR}/model.safetensors" ]; then
  echo "✓ Model already exists at ${TARGET_DIR}/model.safetensors"
  echo "  To re-download, delete it first: rm ${TARGET_DIR}/model.safetensors"
  exit 0
fi

# Download each file
for FILE in "${FILES[@]}"; do
  DEST="${TARGET_DIR}/${FILE}"
  if [ -f "${DEST}" ]; then
    echo "✓ ${FILE} already exists, skipping"
    continue
  fi

  echo "⬇ Downloading ${FILE}..."
  STATUS=$(curl -L -s -o "${DEST}" -w "%{http_code}" "${BASE_URL}/${FILE}")

  if [ "${STATUS}" != "200" ]; then
    echo "✗ Failed to download ${FILE} (HTTP ${STATUS})"
    echo ""
    echo "The model.safetensors file (256MB) may fail on unstable connections."
    echo "Alternative download methods:"
    echo ""
    echo "  1. Manual download from browser:"
    echo "     ${BASE_URL}/model.safetensors"
    echo ""
    echo "  2. Use git-lfs (if hosted):"
    echo "     git lfs install"
    echo "     git clone https://github.com/${REPO}.git --filter=blob:none"
    echo ""
    echo "  3. Transfer from another machine:"
    echo "     scp model.safetensors ${TARGET_DIR}/"
    rm -f "${DEST}"
    exit 1
  fi

  echo "✓ ${FILE} downloaded"
done

# Verify
echo ""
echo "Verifying..."
EXPECTED_FILES=("config.json" "model.safetensors" "tokenizer.json" "tokenizer_config.json")
ALL_OK=true
for F in "${EXPECTED_FILES[@]}"; do
  if [ ! -f "${TARGET_DIR}/${F}" ]; then
    echo "✗ Missing: ${F}"
    ALL_OK=false
  fi
done

if [ "${ALL_OK}" = true ]; then
  echo ""
  echo "✓ DilBert v3 model installed successfully at ${TARGET_DIR}"
  echo ""
  echo "To use with Remembrance:"
  echo "  pip install -e \".[gate]\""
  echo ""
  echo "The default gate chain (dilbert,heuristic) will now use this model."
else
  echo ""
  echo "✗ Some files are missing. Please re-run this script or download manually."
  exit 1
fi