#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fanza_api}"
BRANCH="${BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$APP_DIR"

echo "[deploy] Fetching latest code for $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[deploy] Preparing Python virtualenv"
if [ ! -d "venv" ]; then
  "$PYTHON_BIN" -m venv venv
fi

source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[deploy] Validating Python files"
python -m compileall -q common queries utils batch_run.py fetch_fanza_rank.py fetch_antenna_rss.py fetch_fc2_videos.py

echo "[deploy] Update complete"
