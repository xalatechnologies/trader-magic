import os
import json
import threading
import time
import requests
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import uuid

from src.config import config
from src.utils import get_logger, TradeSignal, TradingDecision, redis_client

logger = get_logger("crypto_news_client")

class CryptoNewsClient:
    """Alternate news client that fetches cryptocurrency news from public APIs"""
    
    def __init__(self):
        self.openai_api_key = config.openai.api_key
        self.openai_model = config.openai.model
        self.openai_client = None
        self.running = False
        self.thread = None
        self.subscribed_symbols = []  # List of symbols to track for news
        self.impact_threshold_buy = config.features.news_buy_threshold
        self.impact_threshold_sell = config.features.news_sell_threshold
        self.poll_interval = 300  # Poll every 5 minutes by default
        
        # APIs we can use for crypto news
        self.apis = [
            {
                "name": "CryptoCompare News API",
                "url": "https://min-api.cryptocompare.com/data/v2/news/?lang=EN",
                "enabled": True,
                "parser": self._parse_cryptocompare_news
            },
            {
                "name": "Crypto Panic API",
                "url": "https://cryptopanic.com/api/v1/posts/?auth_token=none&public=true&kind=news",
                "enabled": False,  # Enable if you have an API key
                "parser": self._parse_cryptopanic_news
            }
        ]
        
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI package not installed, headline analysis will be disabled")
        else:
            logger.warning("OpenAI API key not set, headline analysis will be disabled")
        
        logger.info(f"Crypto News client initialized with buy threshold: {self.impact_threshold_buy}, sell threshold: {self.impact_threshold_sell}")
    
    def fetch_news(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve recent news for a given crypto symbol from Redis
        
        Args:
            symbol: The trading symbol to get news for (e.g., BTC/USD)
            limit: Maximum number of news items to return
            
        Returns:
            List of news items for the symbol
        """
        try:
            logger.info(f"Fetching crypto news for {symbol}")
            
            # Format the symbol to match what's stored in news data
            formatted_symbol = symbol.split('/')[0] if '/' in symbol else symbol
            
            # Get all news items from Redis
            news_keys = redis_client.client.keys("news:*")
            if not news_keys:
                logger.debug(f"No news found in Redis for {symbol}")
                return []
                
            # Find news matching our symbol
            news_items = []
            
            for key in news_keys:
                news_data = redis_client.get_json(key)
                if not news_data:
                    continue
                    
                # Check if this news item is about our symbol
                symbols = news_data.get('symbols', [])
                if formatted_symbol in symbols:
                    # Add this news item to the list
                    news_items.append(news_data)
                    
            # Sort by timestamp (newest first) and limit results
            news_items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return news_items[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []
    
    def set_subscribed_symbols(self, symbols: List[str]):
        """Set the list of symbols to track for news"""
        # Convert symbols to format expected by news APIs
        formatted_symbols = []
        for symbol in symbols:
            # If it's a crypto pair like BTC/USD, extract just the first part
            if '/' in symbol:
                base_symbol = symbol.split('/')[0]
                formatted_symbols.append(base_symbol)
            else:
                # Regular symbol
                formatted_symbols.append(symbol)
        
        self.subscribed_symbols = formatted_symbols
        logger.info(f"Set subscribed symbols for news: {', '.join(formatted_symbols)}")
    
    def start(self):
        """Start the news client in a background thread"""
        if self.running:
            logger.warning("News client already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._poll_news_sources, daemon=True)
        self.thread.start()
        logger.info("Started crypto news client background thread")
    
    def stop(self):
        """Stop the news client"""
        self.running = False
        logger.info("Stopping crypto news client")
    
    def _poll_news_sources(self):
        """Poll news sources at regular intervals"""
        logger.info(f"Starting to poll news sources every {self.poll_interval} seconds")
        
        # Wait 10 seconds before first poll to allow system to initialize
        time.sleep(10)
        
        while self.running:
            try:
                logger.info("Polling news sources...")
                
                # Try each API source until one works
                for api in self.apis:
                    if not api["enabled"]:
                        continue
                        
                    try:
                        logger.info(f"Fetching news from {api['name']}...")
                        response = requests.get(api["url"], timeout=10)
                        
                        if response.status_code == 200:
                            news_items = api["parser"](response.json())
                            if news_items:
                                logger.info(f"Successfully fetched {len(news_items)} news items from {api['name']}")
                                for item in news_items:
                                    self._process_news_item(item)
                                break
                        else:
                            logger.warning(f"Failed to fetch news from {api['name']}: Status {response.status_code}")
                    except Exception as e:
                        logger.error(f"Error fetching news from {api['name']}: {e}")
                
            except Exception as e:
                logger.error(f"Error in news polling loop: {e}")
            
            # Sleep until next poll
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _parse_cryptocompare_news(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse news data from CryptoCompare API"""
        if not data or "Data" not in data:
            return []
            
        news_items = []
        for item in data["Data"]:
            # Extract relevant crypto symbols from categories and tags
            symbols = []
            
            # Extract from categories
            categories = item.get("categories", "").split("|")
            for category in categories:
                if category in self.subscribed_symbols:
                    symbols.append(category)
            
            # Extract from tags
            tags = item.get("tags", "").split("|")
            for tag in tags:
                if tag in self.subscribed_symbols:
                    symbols.append(tag)
                    
            # If no specific symbols found but we're tracking BTC, 
            # include general crypto news with BTC
            if not symbols and "BTC" in self.subscribed_symbols:
                symbols.append("BTC")
                
            # Skip if no relevant symbols
            if not symbols:
                continue
                
            # Create news item
            news_item = {
                "id": item.get("id", str(uuid.uuid4())),
                "headline": item.get("title", ""),
                "summary": item.get("body", "")[:200] + "...",
                "symbols": list(set(symbols)),  # Remove duplicates
                "source": item.get("source", "CryptoCompare"),
                "url": item.get("url", ""),
                "timestamp": datetime.fromtimestamp(item.get("published_on", time.time())).isoformat()
            }
            
            news_items.append(news_item)
            
        return news_items
    
    def _parse_cryptopanic_news(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse news data from CryptoPanic API"""
        if not data or "results" not in data:
            return []
            
        news_items = []
        for item in data["results"]:
            # Extract relevant crypto symbols from currencies
            symbols = []
            for currency in item.get("currencies", []):
                code = currency.get("code", "")
                if code in self.subscribed_symbols:
                    symbols.append(code)
                    
            # Skip if no relevant symbols
            if not symbols:
                continue
                
            # Create news item
            news_item = {
                "id": str(item.get("id", str(uuid.uuid4()))),
                "headline": item.get("title", ""),
                "summary": item.get("body", "")[:200] + "..." if item.get("body") else "",
                "symbols": symbols,
                "source": item.get("source", {}).get("title", "CryptoPanic"),
                "url": item.get("url", ""),
                "timestamp": item.get("created_at", datetime.now().isoformat())
            }
            
            news_items.append(news_item)
            
        return news_items
    
    def _process_news_item(self, news_item: Dict[str, Any]):
        """Process a news item and store it in Redis"""
        try:
            # Log the news item
            headline = news_item.get("headline", "")
            symbols = news_item.get("symbols", [])
            logger.info(f"Processing news for {', '.join(symbols)}: {headline}")
            
            # Generate a unique ID if not provided
            if "id" not in news_item:
                news_item["id"] = str(uuid.uuid4())
                
            # Store the news item in Redis
            redis_key = f"news:{news_item['id']}"
            
            # Check if this news item already exists
            existing_news = redis_client.get_json(redis_key)
            if existing_news:
                logger.debug(f"News item already exists in Redis: {redis_key}")
                return
                
            # Save to Redis with a 24-hour TTL
            redis_client.set_json(redis_key, news_item, ttl=86400)  # 24 hour TTL
            
            # Publish a notification so the frontend updates immediately
            redis_client.client.publish('trade_notifications', json.dumps({
                "type": "news_update",
                "symbols": symbols,
                "timestamp": datetime.now().isoformat()
            }))
            
            logger.info(f"Stored news item in Redis with key: {redis_key}")
            
            # If we have OpenAI client, analyze the headline
            if self.openai_client:
                # Analyze headline for each matched symbol
                for symbol in symbols:
                    threading.Thread(
                        target=self._analyze_headline_and_trade,
                        args=(symbol, headline),
                        daemon=True
                    ).start()
            
        except Exception as e:
            logger.error(f"Error processing news item: {e}")
    
    def _analyze_headline_and_trade(self, symbol: str, headline: str):
        """Analyze the headline using OpenAI and execute trades based on the result"""
        try:
            logger.info(f"Analyzing headline for {symbol}: {headline}")
            
            # Ask OpenAI to analyze the headline
            completion = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "Only respond with a number from 1-100 detailing the impact of the headline."},
                    {"role": "user", "content": f"Given the headline '{headline}', show me a number from 1-100 detailing the impact of this headline for the company {symbol}."}
                ]
            )
            
            # Extract the impact score from the response
            response_content = completion.choices[0].message.content.strip()
            logger.info(f"OpenAI response for {symbol}: {response_content}")
            
            # Try to convert the response to an integer
            try:
                impact_score = int(response_content)
            except ValueError:
                # Try to extract a number from the response
                import re
                match = re.search(r'(\d+)', response_content)
                if match:
                    impact_score = int(match.group(1))
                else:
                    logger.warning(f"Could not extract impact score from response: {response_content}")
                    return
            
            # Ensure the score is within range
            impact_score = max(1, min(impact_score, 100))
            logger.info(f"Extracted impact score for {symbol}: {impact_score}")
            
            # Update the news item in Redis with the impact score
            redis_client.client.publish('trade_notifications', json.dumps({
                "type": "sentiment_update",
                "symbol": symbol,
                "score": impact_score,
                "timestamp": datetime.now().isoformat()
            }))
            
            # Store sentiment data for the symbol
            redis_key = f"news:{symbol}:sentiment"
            sentiment_data = {
                "score": impact_score,
                "headline": headline,
                "timestamp": datetime.now().isoformat()
            }
            redis_client.set_json(redis_key, sentiment_data, ttl=3600)  # 1 hour TTL
            
            logger.info(f"Updated sentiment for {symbol}: {impact_score}")
            
            # Take trading action based on sentiment
            if impact_score >= self.impact_threshold_buy:
                logger.info(f"POSITIVE sentiment for {symbol}: {impact_score} >= {self.impact_threshold_buy}")
                
                # Create a buy signal based on the news
                signal = TradeSignal(
                    symbol=symbol,
                    decision=TradingDecision.BUY,
                    confidence=min(0.9, impact_score / 100),
                    # Include the impact score in the metadata
                    metadata={
                        "news_sentiment": impact_score,
                        "headline": headline
                    }
                )
                
                # Store the signal in Redis
                signal_key = f"signal:{symbol}"
                redis_client.set_json(signal_key, signal.to_dict())
                logger.info(f"Created BUY signal for {symbol} based on news sentiment")
                
            elif impact_score <= self.impact_threshold_sell:
                logger.info(f"NEGATIVE sentiment for {symbol}: {impact_score} <= {self.impact_threshold_sell}")
                
                # Create a sell signal based on the news
                signal = TradeSignal(
                    symbol=symbol,
                    decision=TradingDecision.SELL,
                    confidence=min(0.9, (100 - impact_score) / 100),
                    # Include the impact score in the metadata
                    metadata={
                        "news_sentiment": impact_score,
                        "headline": headline
                    }
                )
                
                # Store the signal in Redis
                signal_key = f"signal:{symbol}"
                redis_client.set_json(signal_key, signal.to_dict())
                logger.info(f"Created SELL signal for {symbol} based on news sentiment")
                
            else:
                logger.info(f"NEUTRAL sentiment for {symbol}: {self.impact_threshold_sell} < {impact_score} < {self.impact_threshold_buy}")
        
        except Exception as e:
            logger.error(f"Error analyzing headline: {e}")

# Create a singleton instance
crypto_news_client = CryptoNewsClient() 