import os
import time
import json
from src.data_retrieval.crypto_news_client import crypto_news_client
from src.utils import redis_client
from src.config import config

def populate_crypto_news():
    """Script to fetch and populate crypto news from alternative APIs"""
    print("Starting crypto news fetcher...")
    
    # Get configured symbols
    symbols = config.trading.symbols
    print(f"Configured symbols: {', '.join(symbols)}")
    
    # Set symbols in the news client
    crypto_news_client.set_subscribed_symbols(symbols)
    
    # Check if we have any existing news
    news_keys = redis_client.client.keys("news:*")
    print(f"Found {len(news_keys)} existing news items in Redis")
    
    # Clear existing news if requested
    if len(news_keys) > 0 and input("Do you want to clear existing news? (y/n): ").lower() == 'y':
        for key in news_keys:
            redis_client.client.delete(key)
        print("Cleared existing news")
    
    # Manually trigger news fetch
    print("Fetching news from CryptoCompare...")
    
    # Get all enabled API configs
    enabled_apis = [api for api in crypto_news_client.apis if api["enabled"]]
    
    for api in enabled_apis:
        try:
            import requests
            print(f"Fetching from {api['name']}...")
            response = requests.get(api["url"], timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_items = api["parser"](data)
                
                print(f"Fetched {len(news_items)} news items from {api['name']}")
                
                # Process each news item
                for item in news_items:
                    crypto_news_client._process_news_item(item)
                    # Small delay to avoid OpenAI rate limiting if we're using sentiment analysis
                    time.sleep(0.5)
            else:
                print(f"Failed to fetch from {api['name']}: Status {response.status_code}")
        except Exception as e:
            print(f"Error fetching from {api['name']}: {str(e)}")
    
    # Check news in Redis
    news_keys = redis_client.client.keys("news:*")
    print(f"Now have {len(news_keys)} news items in Redis")
    
    # Print a few news items as example
    for key in news_keys[:5]:
        try:
            news_data = redis_client.get_json(key)
            if news_data:
                print(f"\nHeadline: {news_data.get('headline')}")
                print(f"Symbols: {', '.join(news_data.get('symbols', []))}")
                print(f"Source: {news_data.get('source')}")
                print(f"URL: {news_data.get('url')}")
        except:
            pass
    
    print("\nNews fetching completed!")
    print("The news feed should now be populated on the dashboard.")
    print("Restart the frontend to ensure the news feed is refreshed: docker restart frontend")

if __name__ == "__main__":
    populate_crypto_news() 