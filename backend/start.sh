#!/usr/bin/env sh
# Start the FastAPI backend. Mirrors the root Procfile so local runs and
# platform deploys use the same command.
#
#   ./start.sh          production-style (no reload), port $PORT or 8000
#   ./start.sh --dev    auto-reload for development
#
# Requires: pip install -r requirements.txt, and a .env (see README).
cd "$(dirname "$0")"

if [ "$1" = "--dev" ]; then
  exec uvicorn app.main:app --reload --port "${PORT:-8000}"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
