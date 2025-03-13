import os
import json
import redis
from datetime import datetime

def reload_api_keys():
    """
    Force the system to reload API keys from the .env file
    by clearing any cached keys in Redis
    """
    print("🔑 Reloading API keys from .env file...")
    
    # Connect to Redis
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_db = int(os.getenv('REDIS_DB', 0))
    
    try:
        r = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=redis_db, 
            decode_responses=True
        )
        
        # Clear account cache to force reload
        r.delete('account_summary')
        print("✅ Cleared account_summary cache")
        
        # Clear account data
        r.delete('account:data')
        print("✅ Cleared account:data cache")
        
        # Delete any cached API keys 
        api_keys = r.keys("api_key:*")
        if api_keys:
            for key in api_keys:
                r.delete(key)
                print(f"✅ Deleted cached API key: {key}")
        else:
            print("✅ No cached API keys found")
            
        # Get API keys from .env
        taapi_key = os.getenv('TAAPI_API_KEY', '')
        alpaca_key = os.getenv('ALPACA_API_KEY', '')
        alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
        
        print(f"📊 TAAPI API Key (masked): {mask_key(taapi_key)}")
        print(f"🦙 Alpaca API Key (masked): {mask_key(alpaca_key)}")
        print(f"🦙 Alpaca Secret (masked): {mask_key(alpaca_secret)}")
        
        # Force a notification to reload keys
        notification = {
            "type": "reload_api_keys",
            "timestamp": datetime.now().isoformat()
        }
        r.publish('trade_notifications', json.dumps(notification))
        print("📢 Published API key reload notification")
        
        print("\n✅ API keys will be reloaded from .env file on next service restart")
        print("💡 For immediate effect, restart the trade_execution service:")
        print("   docker restart trade_execution")
        
        return True
    except Exception as e:
        print(f"❌ Error reloading API keys: {e}")
        return False

def mask_key(key):
    """Mask an API key for display, showing only first 4 and last 4 characters"""
    if not key:
        return "Not set"
    if len(key) <= 8:
        return "***" 
    return f"{key[:4]}...{key[-4:]}"

if __name__ == "__main__":
    reload_api_keys() 