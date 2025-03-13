import os
import json
import time
import uuid
import requests
from datetime import datetime

# Connect to Redis
import redis
redis_host = os.getenv('REDIS_HOST', 'redis')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

def fetch_cryptocompare_news():
    """
    Fetch cryptocurrency news from CryptoCompare and store it in Redis
    """
    print("Fetching news from CryptoCompare...")
    
    # Get symbols from environment variable
    symbols_str = os.getenv('SYMBOLS', 'BTC/USDT,ETH/USDT,XRP/USDT,LTC/USDT')
    symbols = symbols_str.split(',')
    
    # Parse symbols to get base assets (BTC, ETH, etc.)
    base_symbols = []
    for symbol in symbols:
        if '/' in symbol:
            base_symbols.append(symbol.split('/')[0])
        else:
            base_symbols.append(symbol)
    
    print(f"Looking for news related to: {', '.join(base_symbols)}")
    
    # Fetch news from CryptoCompare
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"Error fetching news: Status code {response.status_code}")
            return False
        
        data = response.json()
        if "Data" not in data:
            print("No news data found in the response")
            return False
        
        # Process news items
        news_count = 0
        for item in data["Data"]:
            # Find relevant symbols in categories or tags
            item_symbols = []
            
            # Check categories
            categories = item.get("categories", "").split("|")
            for category in categories:
                if category in base_symbols:
                    item_symbols.append(category)
            
            # Check tags
            tags = item.get("tags", "").split("|")
            for tag in tags:
                if tag in base_symbols:
                    item_symbols.append(tag)
                    
            # If this news is for Bitcoin and we have BTC symbol
            if ("BTC" in base_symbols or "Bitcoin" in base_symbols) and ("BTC" in item.get("categories", "") or "Bitcoin" in item.get("categories", "")):
                if "BTC" in base_symbols:
                    item_symbols.append("BTC")
                else:
                    item_symbols.append("Bitcoin")
            
            # Skip if not relevant to our symbols
            if not item_symbols and "BTC" in base_symbols:
                # Include general crypto news with BTC if no specific match
                item_symbols.append("BTC")
            elif not item_symbols:
                continue
            
            # Format news item
            news_id = str(item.get("id", str(uuid.uuid4())))
            news_data = {
                "id": news_id,
                "headline": item.get("title", ""),
                "summary": item.get("body", "")[:200] + "..." if item.get("body") else "",
                "symbols": list(set(item_symbols)),  # Remove duplicates
                "source": item.get("source", "CryptoCompare"),
                "url": item.get("url", ""),
                "timestamp": datetime.fromtimestamp(item.get("published_on", time.time())).isoformat()
            }
            
            # Store in Redis with 24-hour TTL
            redis_key = f"news:{news_id}"
            
            # Check if news already exists
            existing = redis_client.get(redis_key)
            if existing:
                continue
                
            redis_client.set(redis_key, json.dumps(news_data))
            redis_client.expire(redis_key, 86400)  # 24-hour TTL
            news_count += 1
            
            # Publish notification for frontend update
            redis_client.publish('trade_notifications', json.dumps({
                "type": "news_update",
                "symbols": news_data["symbols"],
                "timestamp": datetime.now().isoformat()
            }))
            
            print(f"Added news: {news_data['headline'][:50]}...")
        
        print(f"Successfully added {news_count} news items to Redis")
        return True
    
    except Exception as e:
        print(f"Error fetching news: {e}")
        return False

def print_stored_news():
    """
    Print all news items stored in Redis
    """
    print("\nStored news items:")
    
    # Get all news keys
    news_keys = redis_client.keys("news:*")
    print(f"Found {len(news_keys)} news items")
    
    # Print a sample of news items
    for key in news_keys[:5]:
        news_data = redis_client.get(key)
        if news_data:
            try:
                news = json.loads(news_data)
                print(f"\nHeadline: {news.get('headline', '')[:70]}...")
                print(f"Symbols: {', '.join(news.get('symbols', []))}")
                print(f"Source: {news.get('source', 'Unknown')}")
                print(f"URL: {news.get('url', 'No URL')}")
            except:
                print(f"Error parsing news data for key: {key}")
    
    # Now notify the frontend to update
    redis_client.publish('trade_notifications', json.dumps({
        "type": "refresh_news",
        "timestamp": datetime.now().isoformat()
    }))
    
    print("\nSent notification to frontend to refresh news")
    print("The news feed should now be populated on the dashboard.")
    print("You may need to refresh your browser to see the updates.")

if __name__ == "__main__":
    # Clear existing news
    if input("Do you want to clear existing news? (y/n): ").lower() == 'y':
        news_keys = redis_client.keys("news:*")
        for key in news_keys:
            redis_client.delete(key)
        print(f"Cleared {len(news_keys)} existing news items")
    
    # Fetch news
    fetch_cryptocompare_news()
    
    # Print stored news
    print_stored_news() 