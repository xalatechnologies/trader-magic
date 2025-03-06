#!/bin/bash
# restart.sh - Utility script to restart all TraderMagic services
#
# This script:
# 1. Stops all containers
# 2. Rebuilds frontend and redis first (dependencies)
# 3. Waits for redis to be fully ready
# 4. Starts all remaining services
#
# Usage: ./restart.sh
# Author: Claude AI

echo "=================================================="
echo "    TraderMagic - Service Restart Utility        "
echo "=================================================="
echo "Stopping and rebuilding TraderMagic containers..."
docker compose down

echo "Building and starting core dependencies first..."
docker compose up -d --build frontend redis

echo "Waiting for Redis to initialize (3 seconds)..."
sleep 3

echo "Forcing trading to disabled state for safety..."
docker compose exec redis redis-cli set trading_enabled false

echo "Starting remaining trading services..."
docker compose up -d

echo "=================================================="
echo "All services are now running!"
echo "Web UI is available at: http://localhost:9753"
echo ""
echo "Use 'docker compose logs -f' to follow the logs"
echo "=================================================="