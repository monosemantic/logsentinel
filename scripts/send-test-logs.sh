#!/bin/bash
# scripts/send-test-logs.sh
# Fires a sequence of test logs that walks through the full AFD state machine.
# Run AFTER demo-start.sh is up and you have the ngrok URL.
# Usage: bash scripts/send-test-logs.sh [WEBHOOK_URL]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Accept URL as argument, fall back to reading from ngrok local API, then .env
if [ -n "$1" ]; then
  BASE_URL="$1"
else
  BASE_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null \
    || echo "")
fi

if [ -z "$BASE_URL" ]; then
  echo "Could not detect ngrok URL. Pass it as an argument:"
  echo "  bash scripts/send-test-logs.sh https://xxxx.ngrok-free.app"
  exit 1
fi

ENDPOINT="${BASE_URL}/webhook/logs"

# Source .env for WEBHOOK_SECRET
if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

SECRET="${WEBHOOK_SECRET:-}"
AUTH_HEADER=""
if [ -n "$SECRET" ]; then
  AUTH_HEADER="-H 'X-Webhook-Secret: ${SECRET}'"
fi

send_log() {
  local label="$1"
  local payload="$2"
  local delay="${3:-2}"
  echo -e "${YELLOW}[$label]${NC} Sending..."
  eval "curl -s -X POST '$ENDPOINT' \
    -H 'Content-Type: application/json' \
    $AUTH_HEADER \
    -d '$payload'" | python3 -c "import sys,json; r=json.load(sys.stdin); print('  status:', r.get('status', r))" 2>/dev/null || echo "  (no JSON response)"
  sleep "$delay"
}

echo -e "\n${GREEN}LogSentinel demo sequence — target: $ENDPOINT${NC}\n"

# 1. INFO — state should stay INFO
send_log "1/6 INFO" \
  '{"raw_log":"2024-01-15 10:00:00 INFO Server started on port 8080 — healthy","source_id":"demo-service"}' 2

# 2. WARNING — state should move to WARNING
send_log "2/6 WARNING" \
  '{"raw_log":"2024-01-15 10:01:00 WARNING: Response time 2340ms exceeds SLA threshold (800ms)","source_id":"demo-service"}' 2

# 3. ERROR — state should move to ERROR, cascade_count=1
send_log "3/6 ERROR (1/3)" \
  '{"raw_log":"2024-01-15 10:02:00 ERROR Connection refused to postgres://db-primary:5432 after 3 retries","source_id":"demo-service"}' 3

# 4. ERROR again — cascade_count=2
send_log "4/6 ERROR (2/3)" \
  '{"raw_log":"2024-01-15 10:02:15 ERROR Connection refused to postgres://db-primary:5432 after 3 retries","source_id":"demo-service"}' 3

# 5. ERROR again — cascade_count=3, state should flip to ERROR_CASCADE
send_log "5/6 ERROR (3/3 — triggers ERROR_CASCADE)" \
  '{"raw_log":"2024-01-15 10:02:28 ERROR Connection refused to postgres://db-primary:5432 after 3 retries","source_id":"demo-service"}' 3

# 6. CRITICAL — state should move to CRITICAL, triggers LLM + WhatsApp alert
# send_log "6/6 CRITICAL" \
#   '{"raw_log":"2024-01-15 10:03:00 CRITICAL: Database connection pool exhausted — all 50 connections in use, new requests rejected","source_id":"demo-service"}' 2

echo ""
echo -e "${GREEN}Sequence complete. Check:${NC}"
echo "  - n8n execution log:  http://localhost:5678"
echo "  - DB state:  docker exec logsentinel-postgres psql -U n8n -d logsentinel -c \"SELECT source_id, current_state, cascade_count FROM afd_states WHERE source_id='demo-service';\""
echo "  - Your WhatsApp for the CRITICAL alert"
echo ""