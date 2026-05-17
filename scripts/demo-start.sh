#!/bin/bash
# scripts/demo-start.sh
# Starts LogSentinel in demo mode with a public ngrok tunnel.
# Usage: bash scripts/demo-start.sh
# Requires: Docker, docker compose v2, a .env with NGROK_AUTHTOKEN set.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_BASE="docker-compose.yml"
COMPOSE_DEMO="docker-compose.override.demo.yml"

# ── 1. Preflight checks ───────────────────────────────────────────────────────

echo -e "${BLUE}LogSentinel Demo Mode${NC}"
echo "---"

if ! docker compose version &>/dev/null; then
  echo -e "${RED}Error: docker compose v2 not found. Install Docker Desktop >= 4.x.${NC}"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo -e "${RED}Error: .env file not found. Copy .env.example and fill in the values.${NC}"
  exit 1
fi

# Source .env so we can check values here too
set -a; source .env; set +a

if [ -z "$NGROK_AUTHTOKEN" ] || [ "$NGROK_AUTHTOKEN" = "CHANGE_ME" ]; then
  echo -e "${RED}Error: NGROK_AUTHTOKEN is not set in .env.${NC}"
  echo "  Get your free token at: https://dashboard.ngrok.com/get-started/your-authtoken"
  exit 1
fi

# ── 2. Start core services (postgres + n8n) first ────────────────────────────

echo -e "\n${YELLOW}Starting postgres and n8n...${NC}"
docker compose -f "$COMPOSE_BASE" up -d postgres n8n

echo -e "${YELLOW}Waiting for n8n to be healthy...${NC}"
ATTEMPTS=0
MAX_ATTEMPTS=30
until docker compose -f "$COMPOSE_BASE" ps n8n | grep -q "healthy"; do
  sleep 3
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
    echo -e "${RED}Timed out waiting for n8n to be healthy. Check logs:${NC}"
    echo "  docker compose logs n8n --tail=50"
    exit 1
  fi
  echo -n "."
done
echo ""

# ── 3. Start ngrok ───────────────────────────────────────────────────────────

echo -e "${YELLOW}Starting ngrok tunnel...${NC}"
docker compose -f "$COMPOSE_BASE" -f "$COMPOSE_DEMO" up -d ngrok

# Wait for ngrok API to be ready (it takes a second after the container starts)
ATTEMPTS=0
NGROK_URL=""
until [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; do
  sleep 2
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ $ATTEMPTS -ge 15 ]; then
    echo -e "${RED}Could not get ngrok URL from the local API. Possible causes:${NC}"
    echo "  - Invalid NGROK_AUTHTOKEN"
    echo "  - ngrok container failed to start"
    echo "  Check with: docker compose logs ngrok"
    exit 1
  fi
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || echo "")
done

# ── 4. Update WEBHOOK_URL so n8n uses the ngrok URL for webhook generation ───

echo -e "${YELLOW}Restarting n8n with WEBHOOK_URL=${NGROK_URL}...${NC}"
NGROK_URL="$NGROK_URL" docker compose -f "$COMPOSE_BASE" -f "$COMPOSE_DEMO" up -d n8n

# Brief wait for n8n to restart
sleep 5

# ── 5. Print connection info ──────────────────────────────────────────────────

WEBHOOK_ENDPOINT="${NGROK_URL}/webhook/logs"

echo ""
echo -e "${GREEN}LogSentinel is running in demo mode.${NC}"
echo ""
echo "  n8n UI          : http://localhost:5678"
echo "  ngrok dashboard : http://localhost:4040"
echo ""
echo -e "${GREEN}Public webhook endpoint:${NC}"
echo ""
echo "  $WEBHOOK_ENDPOINT"
echo ""
echo "--- Quick test (run this in another terminal) ---"
echo ""
echo "  curl -X POST $WEBHOOK_ENDPOINT \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-Webhook-Secret: \$WEBHOOK_SECRET' \\"
echo "    -d '{\"raw_log\":\"2024-01-15 10:00:00 CRITICAL: DB connection pool exhausted\",\"source_id\":\"demo-service\"}'"
echo ""
echo "--- Twilio WhatsApp sandbox (if not yet configured) ---"
echo ""
echo "  1. Go to https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn"
echo "  2. Send 'join <your-sandbox-keyword>' to +14155238886 on WhatsApp"
echo "  3. In Twilio console, set the webhook URL to:"
echo "     ${NGROK_URL}/webhook/whatsapp-feedback"
echo ""
echo -e "${YELLOW}Note: ngrok URL changes every restart. Update Twilio and .env after each demo startup.${NC}"
echo ""