import json
import redis
import os
from datetime import datetime

# Connect to Redis
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port)

# Create a proper trade result for LTC/USDT
ltc_result = {
    "symbol": "LTC/USDT",
    "decision": "buy",
    "order_id": "test-ltc-buy-3",
    "quantity": 1.5,
    "price": 97.25,
    "status": "executed",
    "error": None,
    "timestamp": datetime.now().isoformat()
}

# Store in Redis
redis_key = "trade_result:LTC/USDT"
redis_client.set(redis_key, json.dumps(ltc_result))
print(f"Updated {redis_key} with status: {ltc_result['status']}")

# Publish keyspace notification
redis_client.publish(f'__keyspace@0__:{redis_key}', 'set')
print(f"Published notification for {redis_key}")

# Verify the result
result = redis_client.get(redis_key)
if result:
    result_json = json.loads(result)
    print(f"Verified result: {result_json['status']}")
else:
    print("Failed to verify result") 