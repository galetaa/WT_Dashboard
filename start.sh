#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
    echo "Create .venv and install backend/requirements.txt first (see README.md)." >&2
    exit 1
fi

exec "$PROJECT_DIR/.venv/bin/python" -m uvicorn main:app \
    --app-dir "$PROJECT_DIR/backend" --host 127.0.0.1 --port 8765
