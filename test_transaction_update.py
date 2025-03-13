import json
import redis
import os
import time
from datetime import datetime

# Connect to Redis
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port)

def create_test_transaction(symbol, decision='buy'):
    """Create a test transaction for the specified symbol"""
    print(f"Creating test transaction for {symbol}...")
    
    # Get current time with microseconds for uniqueness
    current_time = datetime.now().isoformat()
    
    # Create a proper trade result with very distinctive values
    test_result = {
        "symbol": symbol,
        "decision": decision,
        "order_id": f"test-{symbol.replace('/', '-').lower()}-{int(time.time())}",
        "quantity": 9.99,  # Distinctive quantity for easy identification
        "price": 123.45,   # Distinctive price for easy identification
        "status": "executed",
        "error": None,
        "timestamp": current_time
    }
    
    print(f"Transaction details: {json.dumps(test_result, indent=2)}")
    
    # Store in Redis
    redis_key = f"trade_result:{symbol}"
    redis_client.set(redis_key, json.dumps(test_result))
    print(f"Updated {redis_key} with status: {test_result['status']}")
    
    # Publish keyspace notification to trigger the frontend update
    notification_channel = f'__keyspace@0__:{redis_key}'
    subscribers = redis_client.publish(notification_channel, 'set')
    print(f"Published keyspace notification to {notification_channel}, received by {subscribers} subscribers")
    
    # Wait a moment for notification to be processed
    time.sleep(0.5)
    
    # Test direct publication to trade_notifications channel
    trade_notification = {
        "type": "trade_executed",
        "symbol": symbol,
        "timestamp": current_time
    }
    trade_subscribers = redis_client.publish('trade_notifications', json.dumps(trade_notification))
    print(f"Published to trade_notifications channel, received by {trade_subscribers} subscribers")
    
    # Verify the result was stored
    result = redis_client.get(redis_key)
    if result:
        result_json = json.loads(result)
        print(f"Verified result: {result_json['status']} for {symbol} at {result_json['price']}")
        return True
    else:
        print("Failed to verify result")
        return False

if __name__ == "__main__":
    # Get symbol from command line or use default
    import sys
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    else:
        symbol = "BTC/USDT"
        
    decision = 'buy'
    if len(sys.argv) > 2:
        decision = sys.argv[2].lower()
        
    print(f"Testing transaction update for {symbol} with decision: {decision}")
    success = create_test_transaction(symbol, decision)
    
    if success:
        print("\n✅ Test transaction created successfully!")
        print("The frontend should update automatically if Socket.IO is working correctly.")
        print("You can check the frontend logs to verify that the transaction_complete event was received.")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} SYMBOL DECISION")
        print("  Example: python test_transaction_update.py LTC/USDT sell")
    else:
        print("\n❌ Test transaction failed!") 