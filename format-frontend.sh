#!/bin/bash
# Run Prettier formatting on the frontend directory.
# Use --check to verify without modifying files (e.g. in CI).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

cd "$FRONTEND_DIR"

if [[ "$1" == "--check" ]]; then
  echo "Checking frontend formatting..."
  npx prettier --check .
  echo "All files are correctly formatted."
else
  echo "Formatting frontend files..."
  npx prettier --write .
  echo "Done."
fi
