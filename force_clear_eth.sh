#\!/bin/bash
echo "Clearing ETH/USDT trade data from Redis..."
docker compose exec -T redis redis-cli del 'trade_result:ETH/USDT'
docker compose exec -T redis redis-cli del 'signal:ETH/USDT'
echo "Done. Refresh your browser to see the changes."
