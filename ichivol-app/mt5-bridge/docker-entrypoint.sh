#!/bin/bash
# One-time Wine/Windows-Python/MT5 bootstrap (idempotent -- skips steps
# already done in the persisted /root/.wine volume), then starts the
# mt5linux RPyC server and the FastAPI wrapper.
#
# VERIFY-ON-DEPLOY: the exact winetricks/python-under-wine incantations
# below are the highest-risk part of this whole container (see
# README.md). If a step fails, the error from `wine` / `winetricks` itself
# is almost always more informative than anything this script could add --
# `set -x` is left on so it shows up in `docker logs ichivol-mt5-bridge`.
set -euo pipefail
set -x

WINE_PYTHON_DIR="/root/.wine/drive_c/Python311"
WINE_PYTHON="${WINE_PYTHON_DIR}/python.exe"
MT5_TERMINAL_DIR="/root/.wine/drive_c/Program Files/MetaTrader 5"
MT5LINUX_PORT="${MT5LINUX_PORT:-18812}"

# Virtual display -- Wine/MT5's GUI needs one even though nothing is ever
# viewed live (VNC for manual login is layered separately, see README.md).
Xvfb :0 -screen 0 1024x768x16 &
export DISPLAY=:0
sleep 2

if [ ! -f "$WINE_PYTHON" ]; then
    echo "[bootstrap] Installing Windows Python 3.11 under Wine (first boot only)..."
    curl -fsSL -o /tmp/python-installer.exe \
        https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    wine /tmp/python-installer.exe /quiet InstallAllUsers=1 TargetDir="C:\\Python311" PrependPath=1
    rm -f /tmp/python-installer.exe
fi

echo "[bootstrap] Installing MetaTrader5 + mt5linux inside the Windows python..."
wine "$WINE_PYTHON" -m pip install --quiet --no-cache-dir MetaTrader5 mt5linux

if [ ! -d "$MT5_TERMINAL_DIR" ]; then
    echo "[bootstrap] Installing MetaTrader 5 terminal (first boot only)..."
    echo "[bootstrap] MT5_TERMINAL_INSTALLER_URL must point at your broker's"
    echo "[bootstrap] own installer (generic MetaQuotes builds also work read-only)."
    curl -fsSL -o /tmp/mt5setup.exe "${MT5_TERMINAL_INSTALLER_URL:-https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe}"
    wine /tmp/mt5setup.exe /auto
    rm -f /tmp/mt5setup.exe
fi

echo "[bootstrap] Starting mt5linux RPyC server on :${MT5LINUX_PORT}..."
wine "$WINE_PYTHON" -m mt5linux --host 0.0.0.0 -p "$MT5LINUX_PORT" &
MT5LINUX_PID=$!

echo "[bootstrap] Waiting for mt5linux server to accept connections..."
for _ in $(seq 1 30); do
    if (echo > "/dev/tcp/127.0.0.1/${MT5LINUX_PORT}") >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo "[bootstrap] Starting FastAPI bridge wrapper on :8000..."
export MT5LINUX_HOST=127.0.0.1
export MT5LINUX_PORT
exec uvicorn bridge_server:app --host 0.0.0.0 --port 8000
