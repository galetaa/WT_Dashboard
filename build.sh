#!/bin/sh
# Build natively on Linux or macOS; output includes a portable release archive.
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUILD_PYTHON="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$BUILD_PYTHON" ]; then
    BUILD_PYTHON=python3
fi
"$BUILD_PYTHON" -m pip install -r "$PROJECT_DIR/backend/requirements.txt" pyinstaller
exec "$BUILD_PYTHON" "$PROJECT_DIR/scripts/build_release.py"
