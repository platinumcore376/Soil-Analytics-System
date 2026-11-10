# Start the FastAPI backend on Windows. Mirrors the root Procfile so local runs
# and platform deploys use the same command.
#
#   .\start.ps1         production-style (no reload), port $env:PORT or 8000
#   .\start.ps1 -Dev    auto-reload for development
#
# Requires: pip install -r requirements.txt, and a .env (see README).
param([switch]$Dev)

Set-Location $PSScriptRoot
$port = if ($env:PORT) { $env:PORT } else { 8000 }

if ($Dev) {
  uvicorn app.main:app --reload --port $port
} else {
  uvicorn app.main:app --host 0.0.0.0 --port $port
}
