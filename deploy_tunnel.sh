#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# TradeVision — Launch Script
# Starts the FastAPI backend + Cloudflare Quick Tunnel
#
# Usage:
#   chmod +x deploy_tunnel.sh
#   ./deploy_tunnel.sh
#
# The script will print the public HTTPS tunnel URL.
# Copy it → paste into Streamlit Cloud secrets as TRADEVISION_API_URL.
# ─────────────────────────────────────────────────────────────────────────────

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_DIR/venv/bin/activate"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "  🛡️  TradeVision — Deploy Script"
echo "  ─────────────────────────────────"
echo ""

# ── 1. Start FastAPI if not already running ──────────────────────────────────
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || true)

if [ "$API_STATUS" = "200" ]; then
    echo "  ✅ FastAPI already running on :8000"
else
    echo "  🚀 Starting FastAPI backend (loading VLM — ~90s)..."
    source "$VENV"
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 \
        > "$LOG_DIR/api_server.log" 2>&1 &
    API_PID=$!
    echo "     PID: $API_PID"

    # Wait for it to be ready
    echo "  ⏳ Waiting for API to be ready..."
    for i in $(seq 1 36); do
        sleep 5
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || true)
        if [ "$STATUS" = "200" ]; then
            echo "  ✅ API ready!"
            break
        fi
        echo "     Attempt $i/36 (${i}x5s elapsed)..."
    done
fi

echo ""

# ── 2. Check cloudflared is installed ───────────────────────────────────────
if ! command -v cloudflared &> /dev/null; then
    echo "  ❌ cloudflared not installed."
    echo "     Run: wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared-linux-amd64.deb"
    exit 1
fi

echo "  ✅ cloudflared $(cloudflared --version 2>&1 | head -1)"
echo ""

# ── 3. Launch tunnel ────────────────────────────────────────────────────────
TUNNEL_LOG="$LOG_DIR/cloudflare_tunnel.log"
echo "  🌐 Starting Cloudflare Quick Tunnel → http://localhost:8000"
echo "     Log: $TUNNEL_LOG"
echo ""

cloudflared tunnel --url http://localhost:8000 2>&1 | tee "$TUNNEL_LOG" &
TUNNEL_PID=$!

# Extract tunnel URL as soon as it appears
echo "  ⏳ Waiting for tunnel URL..."
for i in $(seq 1 30); do
    sleep 2
    TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
done

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║           🔐 TUNNEL IS LIVE                             ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  API URL  : $TUNNEL_URL"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  NEXT STEPS:                                            ║"
echo "  ║  1. Copy the URL above                                  ║"
echo "  ║  2. Go to share.streamlit.io → App Settings → Secrets   ║"
echo "  ║  3. Add:  TRADEVISION_API_URL = \"$TUNNEL_URL\"     ║"
echo "  ║  4. Save → Reboot app                                   ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Press CTRL+C to collapse the tunnel."
echo ""

# Keep script alive while tunnel runs
wait $TUNNEL_PID
