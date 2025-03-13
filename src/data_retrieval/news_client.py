import os
import json
import threading
import time
from typing import Optional, List, Dict, Any, Callable
import websocket
from openai import OpenAI

from src.config import config
from src.utils import get_logger, TradeSignal, TradingDecision, redis_client

logger = get_logger("news_client")

class AlpacaNewsClient:
    def __init__(self):
        self.ws_url = "wss://stream.data.alpaca.markets/v1beta1/news"
        self.api_key = config.alpaca.api_key
        self.api_secret = config.alpaca.api_secret
        self.openai_api_key = config.openai.api_key
        self.openai_model = config.openai.model
        self.openai_client = None
        self.ws = None
        self.running = False
        self.thread = None
        self.subscribed_symbols = []  # List of symbols to track for news
        self.impact_threshold_buy = config.features.news_buy_threshold
        self.impact_threshold_sell = config.features.news_sell_threshold
        
        # Validate credentials
        if not self.api_key or not self.api_secret:
            logger.error("Alpaca API credentials not set")
            raise ValueError("Alpaca API credentials not set")
            
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI client initialized")
        else:
            logger.warning("OpenAI API key not set, headline analysis will be disabled")
        
        logger.info(f"News client initialized with buy threshold: {self.impact_threshold_buy}, sell threshold: {self.impact_threshold_sell}")
    
    def set_subscribed_symbols(self, symbols: List[str]):
        """Set the list of symbols to track for news"""
        # Convert symbols to format expected by Alpaca news API
        formatted_symbols = []
        for symbol in symbols:
            # If it's a crypto pair like BTC/USD, extract just the first part
            if '/' in symbol:
                base_symbol = symbol.split('/')[0]
                formatted_symbols.append(base_symbol)
            else:
                # Regular stock symbol
                formatted_symbols.append(symbol)
        
        self.subscribed_symbols = formatted_symbols
        logger.info(f"Set subscribed symbols for news: {', '.join(formatted_symbols)}")
        
        # If already connected, update subscription
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self._send_subscribe_message()
    
    def start(self):
        """Start the news client in a background thread"""
        if self.running:
            logger.warning("News client already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.thread.start()
        logger.info("Started news client background thread")
    
    def stop(self):
        """Stop the news client"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("Stopping news client")
    
    def _run_websocket(self):
        """Run the WebSocket connection in a loop, reconnecting on failures"""
        while self.running:
            try:
                # Initialize the WebSocket
                websocket.enableTrace(False)  # Set to True for debugging
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                # Start the WebSocket connection
                self.ws.run_forever()
                
                # Wait before reconnecting
                if self.running:
                    logger.info("WebSocket disconnected, reconnecting in 5 seconds...")
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Error in news WebSocket: {e}")
                if self.running:
                    logger.info("Reconnecting in 10 seconds...")
                    time.sleep(10)
    
    def _on_open(self, ws):
        """Handle WebSocket open event"""
        logger.info("News WebSocket connected")
        
        # Send authentication
        auth_msg = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.api_secret
        }
        ws.send(json.dumps(auth_msg))
        logger.info("Sent authentication message")
        
        # Subscribe to news channels
        self._send_subscribe_message()
    
    def _send_subscribe_message(self):
        """Send subscription message for news channels"""
        if not self.ws:
            logger.error("Cannot subscribe to news: WebSocket not connected")
            return
            
        # If we have specific symbols, subscribe to them
        # Otherwise, subscribe to all news
        if self.subscribed_symbols:
            subscribe_msg = {
                "action": "subscribe",
                "news": self.subscribed_symbols
            }
            logger.info(f"Subscribing to news for specific symbols: {self.subscribed_symbols}")
        else:
            subscribe_msg = {
                "action": "subscribe",
                "news": ["*"]  # Subscribe to all news
            }
            logger.info("Subscribing to ALL news (wildcard)")
        
        try:
            self.ws.send(json.dumps(subscribe_msg))
            
            if self.subscribed_symbols:
                logger.info(f"Subscribed to news for: {', '.join(self.subscribed_symbols)}")
            else:
                logger.info("Subscribed to all news")
        except Exception as e:
            logger.error(f"Error sending news subscription: {e}")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            logger.debug(f"News WebSocket message received: {message[:100]}...")
            data = json.loads(message)
            
            # Handle different message types
            if isinstance(data, list) and len(data) > 0:
                for event in data:
                    if event.get("T") == "n":  # News event
                        logger.info(f"Received news event: {json.dumps(event)[:200]}...")
                        self._handle_news_event(event)
            elif data.get("T") == "success" and data.get("msg") == "authenticated":
                logger.info("Successfully authenticated with Alpaca news stream")
            elif data.get("T") == "subscription" and data.get("msg"):
                logger.info(f"Subscription status: {data.get('msg')}")
            elif data.get("T") == "error":
                logger.error(f"WebSocket error from Alpaca: {data.get('msg')}")
            else:
                logger.debug(f"Unhandled message type: {data}")
            
        except json.JSONDecodeError:
            logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _handle_news_event(self, event):
        """Process news event and determine if trading action is needed"""
        headline = event.get("headline", "")
        symbols = event.get("symbols", [])
        
        if not symbols:
            logger.debug(f"News event with no symbols: {headline}")
            return
            
        logger.info(f"News event for {', '.join(symbols)}: {headline}")
        
        # Store the news event in Redis
        try:
            import uuid
            from datetime import datetime
            
            # Generate a unique ID for this news event
            news_id = str(uuid.uuid4())
            
            # Store the news event for frontend display
            news_data = {
                "id": news_id,
                "headline": headline,
                "symbols": symbols,
                "timestamp": datetime.now().isoformat(),
                "source": event.get("source", "Alpaca"),
                "url": event.get("url", ""),
                "summary": event.get("summary", "")
            }
            
            # Save to Redis with a 24-hour TTL
            redis_key = f"news:{news_id}"
            redis_client.set_json(redis_key, news_data, ttl=86400)  # 24 hour TTL
            
            # Publish a notification so the frontend updates immediately
            redis_client.client.publish('trade_notifications', f"New market news for {', '.join(symbols)}")
            
            logger.info(f"Stored news event in Redis with key: {redis_key}")
        except Exception as e:
            logger.error(f"Error storing news event in Redis: {e}")
        
        # Skip analysis if there's no OpenAI client
        if not self.openai_client:
            logger.warning("OpenAI client not available, skipping headline analysis")
            return
            
        # Match news symbols with our subscribed symbols for trading decisions
        # We need to handle both formats (e.g., "BTC" from news matches with "BTC/USD" in our config)
        matched_symbols = []
        for symbol in symbols:
            # Check if this symbol is directly in our list
            if symbol in self.subscribed_symbols:
                matched_symbols.append(symbol)
            else:
                # Check for partial matches with crypto pairs
                for subscribed in self.subscribed_symbols:
                    # For crypto pairs, the news might use just the base symbol
                    if '/' in subscribed and subscribed.split('/')[0] == symbol:
                        matched_symbols.append(subscribed)
                        break
        
        # Log matched symbols
        if matched_symbols:
            logger.info(f"News symbols matched with our configured symbols: {matched_symbols}")
        else:
            logger.info(f"News symbols {symbols} did not match any of our configured symbols")
            return
                
        # Analyze headline for each matched symbol
        for symbol in matched_symbols:
            threading.Thread(
                target=self._analyze_headline_and_trade,
                args=(symbol, headline),
                daemon=True
            ).start()
    
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
            
            try:
                impact_score = int(response_content)
                logger.info(f"Headline impact for {symbol}: {impact_score}/100")
                
                # Make trading decision based on impact score
                if impact_score >= self.impact_threshold_buy:
                    # Generate a buy signal
                    logger.info(f"Generating BUY signal for {symbol} based on high impact news (score: {impact_score})")
                    self._generate_trade_signal(symbol, TradingDecision.BUY, impact_score)
                elif impact_score <= self.impact_threshold_sell:
                    # Generate a sell signal
                    logger.info(f"Generating SELL signal for {symbol} based on negative news (score: {impact_score})")
                    self._generate_trade_signal(symbol, TradingDecision.SELL, impact_score)
                else:
                    # No action needed
                    logger.info(f"No trading action for {symbol}, impact score {impact_score} is in neutral range")
            except ValueError:
                logger.error(f"Failed to parse impact score from OpenAI response: {response_content}")
            
        except Exception as e:
            logger.error(f"Error analyzing headline for {symbol}: {e}")
    
    def _generate_trade_signal(self, symbol: str, decision: TradingDecision, impact_score: int):
        """Generate and submit a trade signal"""
        # Convert impact_score (1-100) to confidence (0-1)
        confidence = impact_score / 100
        
        # Create a trade signal
        signal = TradeSignal(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            rsi_value=50.0,  # Default RSI value, not used for this strategy
            timestamp=None  # Will use default current time
        )
        
        # Store the signal in Redis for the trade execution service to process
        try:
            signal_key = f"signal:{symbol}"
            redis_client.set_json(signal_key, signal.dict(), ttl=3600)  # 1 hour TTL
            logger.info(f"Stored trade signal in Redis with key {signal_key}: {signal.dict()}")
            
            # Publish a notification so the trade execution service can process it immediately
            redis_client.client.publish('new_trade_signal', symbol)
            logger.info(f"Published trade signal notification for {symbol}")
        except Exception as e:
            logger.error(f"Error storing trade signal for {symbol} in Redis: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        # Attempt to reconnect if the client is still running
        if self.running:
            logger.info("Will attempt to reconnect to news WebSocket in 5 seconds...")

# Singleton instance
news_client = AlpacaNewsClient() 