import os
import json
import redis
from datetime import datetime

def check_api_keys():
    """
    Check which API keys are currently being used by the system
    and compare with what's in the .env file
    """
    print("🔍 Checking API keys...")
    
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
        
        # Get API keys from .env
        env_taapi_key = os.getenv('TAAPI_API_KEY', '')
        env_alpaca_key = os.getenv('ALPACA_API_KEY', '')
        env_alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
        
        print("\n📋 API Keys in .env file:")
        print(f"  TAAPI_API_KEY: {mask_key(env_taapi_key)}")
        print(f"  ALPACA_API_KEY: {mask_key(env_alpaca_key)}")
        print(f"  ALPACA_API_SECRET: {mask_key(env_alpaca_secret)}")
        
        # Check for cached API keys in Redis
        cached_keys = r.keys("api_key:*")
        has_cached_keys = len(cached_keys) > 0
        
        print("\n🗄️ Cached API keys in Redis:")
        if has_cached_keys:
            for key in cached_keys:
                value = r.get(key)
                print(f"  {key}: {mask_key(value)}")
                
            print("\n⚠️ Found cached API keys in Redis which may override .env values!")
            print("   To use the keys from .env, run:\n   python reload_api_keys.py")
        else:
            print("  No cached API keys found - system is likely using keys from .env file")
        
        # Check if account cache exists
        account_cache = r.get('account_summary')
        if account_cache:
            print("\n💾 Account summary is cached in Redis")
            print("   This may contain data from previous API keys")
            print("   To clear cache and use fresh data, run:\n   python reload_api_keys.py")
        else:
            print("\n✅ No account summary cache found")
            
        return has_cached_keys
        
    except Exception as e:
        print(f"❌ Error checking API keys: {e}")
        return False

def mask_key(key):
    """Mask an API key for display, showing only first 4 and last 4 characters"""
    if not key:
        return "Not set"
    if len(key) <= 8:
        return "***" 
    return f"{key[:4]}...{key[-4:]}"

if __name__ == "__main__":
    check_api_keys() 