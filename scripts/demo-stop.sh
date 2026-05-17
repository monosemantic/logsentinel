#!/bin/bash
# scripts/demo-stop.sh
# Stops all LogSentinel demo containers.
# Postgres data is preserved in Docker volumes.

set -e

echo "Stopping LogSentinel demo..."
docker compose -f docker-compose.yml -f docker-compose.override.demo.yml down
echo "Done. Postgres data preserved in logsentinel-postgres-data volume."