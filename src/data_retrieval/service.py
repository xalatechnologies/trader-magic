import time
import uuid
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import config
from src.utils import get_logger, redis_client, RSIData, PriceCandle, PriceHistory, MarketStatus
from src.data_retrieval.taapi_client import taapi_client
from src.data_retrieval.news_client import news_client
from src.data_retrieval.crypto_news_client import crypto_news_client
from src.data_retrieval.polygon_client import PolygonClient

logger = get_logger("data_retrieval_service")

class DataRetrievalService:
    def __init__(self):
        self.symbols = config.trading.symbols
        self.poll_interval = config.trading.poll_interval
        self.price_history_interval = config.taapi.price_history_interval
        self.price_history_limit = config.taapi.price_history_limit
        self.should_run = True
        self.thread = None
        self.use_news_strategy = config.features.news_strategy  # Access the attribute directly
        
        # Use the crypto news client instead of Alpaca news
        self.use_crypto_news = True  # Set to True to use our new crypto news client
        
        # Check if Polygon.io API key is set
        self.use_polygon = bool(config.polygon.api_key)
        
        # Create an instance of PolygonClient
        self.polygon_client = PolygonClient() if self.use_polygon else None
        
        logger.info(f"Data Retrieval Service initialized with symbols: {', '.join(self.symbols)}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Use news strategy: {self.use_news_strategy}")
        logger.info(f"Use Polygon.io API: {self.use_polygon}")
        
        # Check if symbol format includes the new format (stocks)
        self.has_stock_symbols = any(not "/" in symbol for symbol in self.symbols)
        logger.info(f"Has stock symbols: {self.has_stock_symbols}")
        
        # Check if symbol format includes crypto format
        self.has_crypto_symbols = any("/" in symbol for symbol in self.symbols)
        logger.info(f"Has crypto symbols: {self.has_crypto_symbols}")
    
    def start(self):
        """Start the data retrieval service in a background thread"""
        # Start news client if news strategy is enabled
        if self.use_news_strategy:
            if self.use_crypto_news:
                logger.info("Starting crypto news client...")
                crypto_news_client.set_subscribed_symbols(self.symbols)
                crypto_news_client.start()
            else:
                logger.info("Starting Alpaca news client...")
                news_client.set_subscribed_symbols(self.symbols)
                news_client.start()
        
        # Start polling thread
        self.should_run = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        logger.info("Data Retrieval Service started")
    
    def stop(self):
        """Stop the data retrieval service"""
        self.should_run = False
        
        # Stop news client
        if self.use_news_strategy:
            if self.use_crypto_news:
                crypto_news_client.stop()
            else:
                news_client.stop()
                
        logger.info("Data Retrieval Service stopped")

    def _polling_loop(self):
        """Main polling loop to fetch data at regular intervals"""
        logger.info(f"Starting polling loop with interval {self.poll_interval} seconds")
        
        while self.should_run:
            try:
                logger.info("Fetching data for all symbols...")
                self.fetch_all_data()
                
                # Sleep for the configured interval
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                # Continue polling even if there's an error
                time.sleep(10)  # Shorter sleep in case of error
    
    def fetch_all_data(self):
        """Fetch all data types for all symbols"""
        for symbol in self.symbols:
            try:
                # Check if the symbol is a crypto pair or a stock
                is_crypto = "/" in symbol
                is_stock = not is_crypto
                
                logger.info(f"Fetching data for {symbol} ({'crypto' if is_crypto else 'stock'})")
                
                # For stocks, use Polygon.io API if available
                if is_stock and self.use_polygon:
                    logger.info(f"Fetching Polygon.io data for stock symbol {symbol}")
                    self.fetch_polygon_data(symbol)
                
                # For crypto, or if enabled for stocks with RSI
                if is_crypto or (is_stock and config.taapi.fetch_for_stocks):
                    logger.info(f"Fetching TAAPI data for {symbol}")
                    # Fetch RSI data
                    self.fetch_rsi_data(symbol)
                    
                    # Fetch price history for charting
                    self.fetch_price_history(symbol)
                
                # Fetch news for the symbol if news strategy is enabled
                if self.use_news_strategy:
                    if is_crypto and self.use_crypto_news:
                        # Use crypto-specific news client for crypto
                        logger.info(f"Fetching crypto news for {symbol}")
                        crypto_news_client.fetch_news(symbol)
                    else:
                        # Use regular news client for stocks
                        logger.info(f"Fetching regular news for {symbol}")
                        news_client.fetch_news(symbol)
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {str(e)}")
                
        # Update the last poll timestamp in Redis
        redis_client.set('last_data_poll', datetime.now().isoformat())
        logger.info("Data fetch cycle completed")

    def _run_service(self):
        """
        Main service loop - fetches RSI data at regular intervals
        """
        while self.should_run:
            try:
                # For TAAPI's free tier (1 request per 15 seconds), process all symbols
                # at consistent intervals to respect rate limits
                symbols_count = len(self.symbols)
                if symbols_count > 0:
                    # Fixed 16 second interval between API calls for TAAPI free tier
                    # (slightly more than the 15-second minimum to be safe)
                    time_between_symbols = 16
                    logger.info(f"Processing {symbols_count} symbols with {time_between_symbols} seconds between each")
                
                    # Process all symbols in sequence
                    for i, symbol in enumerate(self.symbols):
                        start_time = time.time()
                        logger.info(f"Fetching data for {symbol}")
                        
                        try:
                            # Get RSI data for the symbol
                            rsi_data = taapi_client.get_rsi(symbol)
                            if rsi_data:
                                # Store in Redis
                                redis_key = f"rsi:{symbol}"
                                # Set longer TTL to ensure data is still available for main loop processing
                                redis_client.set_json(redis_key, rsi_data.dict(), ttl=self.poll_interval * 5)
                                logger.info(f"Stored RSI data for {symbol}: {rsi_data.value}")
                                
                                # Get AI decision immediately after getting the data
                                from src.ai_decision import ai_decision_service
                                trade_signal = ai_decision_service.get_decision(rsi_data)
                                if trade_signal:
                                    logger.info(f"Generated trade signal for {symbol}: {trade_signal.decision.value}")
                                    
                                    # Directly execute the trade after generating the signal
                                    if trade_signal.decision.value != "hold":
                                        try:
                                            # NOTE: To avoid potential validation errors,
                                            # we'll use the main module signal-driven approach for trade execution
                                            # rather than executing trades directly from the data retrieval service
                                            
                                            # Simply log that we found a trading opportunity
                                            logger.info(f"Trading opportunity detected for {symbol}: {trade_signal.decision.value}")
                                            logger.info(f"Signal stored in Redis, will be processed by main loop")
                                        except Exception as trade_error:
                                            logger.error(f"Error executing trade from data service: {trade_error}")
                                            
                            # Get price data for the symbol
                            # Add a small delay to respect TAAPI rate limits
                            time.sleep(2)
                            price_data = taapi_client.get_price(symbol)
                            if price_data:
                                # Store in Redis
                                redis_key = f"price:{symbol}"
                                redis_client.set_json(redis_key, price_data, ttl=self.poll_interval * 5)
                                logger.info(f"Stored price data for {symbol}: {price_data['close']}")
                                
                            # Get historical price data for all symbols but stagger them to respect rate limits
                            # Indexes 0, 1, 2, 3, etc. update on cycles 0, 1, 2, 3, etc.
                            current_cycle = int(time.time()) // self.poll_interval
                            if current_cycle % len(self.symbols) == i:
                                time.sleep(2)  # Add delay to respect rate limits
                                logger.info(f"Fetching price history for {symbol} on cycle {current_cycle}")
                                self.update_price_history(symbol)
                            
                            # Calculate remaining time to wait based on elapsed time
                            elapsed = time.time() - start_time
                            wait_time = max(0, time_between_symbols - elapsed)
                            
                            # If this isn't the last symbol, wait before the next one
                            if i < symbols_count - 1 and wait_time > 0:
                                logger.debug(f"Waiting {wait_time:.1f} seconds before next symbol...")
                                time.sleep(wait_time)
                                
                        except Exception as symbol_error:
                            logger.error(f"Error processing symbol {symbol}: {symbol_error}")
                            # Even on error, respect the rate limit timing
                            elapsed = time.time() - start_time
                            wait_time = max(0, time_between_symbols - elapsed)
                            if i < symbols_count - 1 and wait_time > 0:
                                time.sleep(wait_time)
                
                # After processing all symbols, wait until the next poll interval
                remaining_time = max(5, self.poll_interval - (time_between_symbols * symbols_count))
                logger.info(f"Completed processing all symbols. Next poll cycle in {remaining_time:.1f} seconds")
                time.sleep(remaining_time)
            except Exception as e:
                logger.error(f"Error in data retrieval service: {e}")
                time.sleep(10)  # Sleep briefly before retrying

    def get_latest_rsi(self, symbol: str) -> Optional[RSIData]:
        """
        Get the latest RSI data for a symbol from Redis
        """
        redis_key = f"rsi:{symbol}"
        data = redis_client.get_json(redis_key)
        if data:
            # Convert dict back to RSIData
            return RSIData(**data)
        else:
            logger.warning(f"No RSI data found for {symbol}")
            return None
            
    def fetch_rsi_data(self, symbol: str) -> Optional[RSIData]:
        """
        Fetch and store RSI data for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            RSIData object if successful, None if failed
        """
        # Fetch RSI data using the taapi_client
        rsi_data = taapi_client.get_rsi(symbol)
        
        if not rsi_data:
            logger.warning(f"Failed to get RSI data for {symbol}")
            return None
            
        # Store in Redis with appropriate TTL
        redis_key = f"rsi:{symbol}"
        redis_client.set_json(redis_key, rsi_data.dict(), ttl=self.poll_interval * 5)
        logger.info(f"Stored RSI data for {symbol}: {rsi_data.value}")
        
        return rsi_data
            
    def fetch_price_history(self, symbol: str) -> Optional[PriceHistory]:
        """
        Fetch and store historical price data for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            PriceHistory object if successful, None if failed
        """
        interval = self.price_history_interval
        limit = self.price_history_limit
        
        # Fetch historical price data
        price_history_data = taapi_client.get_price_history(symbol, interval, limit)
        if not price_history_data:
            logger.warning(f"Failed to get historical price data for {symbol}")
            return None
            
        # Log the raw data format to help diagnose issues
        logger.debug(f"Raw price history data for {symbol}: {len(price_history_data)} candles")
        if price_history_data and len(price_history_data) > 0:
            logger.debug(f"Sample candle: {price_history_data[0]}")
            
        # Convert to PriceCandle objects
        candles = []
        try:
            for candle in price_history_data:
                # Ensure we have all required fields
                required_fields = ['open', 'high', 'low', 'close', 'volume', 'timestamp']
                for field in required_fields:
                    if field not in candle:
                        logger.error(f"Missing required field '{field}' in candle data: {candle}")
                        continue
                        
                # Create candle object with proper type conversion
                try:
                    # Get market status for this candle (important for stocks)
                    market_status = None
                    
                    # Only check market status for stocks (not crypto)
                    if not taapi_client.crypto_pattern.match(symbol):
                        # For historical data, we need to check if this candle's timestamp falls within market hours
                        # Get the candle's timestamp in Eastern time
                        candle_time = datetime.fromtimestamp(candle['timestamp'], taapi_client.eastern_tz)
                        candle_time_of_day = candle_time.time()
                        candle_weekday = candle_time.weekday()
                        
                        # Weekend
                        if candle_weekday >= 5:
                            market_status = MarketStatus.CLOSED
                        # Regular market hours
                        elif taapi_client.market_open_time <= candle_time_of_day <= taapi_client.market_close_time:
                            market_status = MarketStatus.OPEN
                        # Pre-market
                        elif taapi_client.pre_market_open_time <= candle_time_of_day < taapi_client.market_open_time:
                            market_status = MarketStatus.PRE_MARKET
                        # After-hours
                        elif taapi_client.market_close_time < candle_time_of_day <= taapi_client.after_hours_close_time:
                            market_status = MarketStatus.AFTER_HOURS
                        # Closed
                        else:
                            market_status = MarketStatus.CLOSED
                    else:
                        # Crypto markets are always open
                        market_status = MarketStatus.OPEN
                    
                    price_candle = PriceCandle(
                        symbol=symbol,
                        open=float(candle['open']),
                        high=float(candle['high']),
                        low=float(candle['low']),
                        close=float(candle['close']),
                        volume=float(candle['volume']),
                        timestamp=datetime.fromtimestamp(candle['timestamp']),
                        market_status=market_status
                    )
                    candles.append(price_candle)
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting candle data types for {symbol}: {e}, candle: {candle}")
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error processing candle data for {symbol}: {e}")
            return None
            
        if not candles:
            logger.error(f"No valid candles processed for {symbol}")
            return None
            
        # Add market status summary to log output
        if not taapi_client.crypto_pattern.match(symbol):
            status_counts = {}
            for candle in candles:
                status = candle.market_status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            logger.info(f"Market status summary for {symbol}: {status_counts}")
            
        # Create PriceHistory object
        price_history = PriceHistory(
            symbol=symbol,
            interval=interval,
            candles=candles
        )
        
        # Store in Redis with a much longer TTL to prevent charts disappearing
        redis_key = f"price_history:{symbol}"
        serialized_data = price_history.dict()
        # Use 24 hours instead of 10x poll interval to maintain persistent chart data
        redis_client.set_json(redis_key, serialized_data, ttl=86400) 
        logger.info(f"Stored price history for {symbol}: {len(candles)} candles with 24-hour TTL")
        
        # Verify data was stored correctly
        try:
            verification = redis_client.get_json(redis_key)
            if verification and 'candles' in verification:
                logger.info(f"Verification: Redis has {len(verification['candles'])} candles for {symbol}")
            else:
                logger.error(f"Failed to verify price history data in Redis for {symbol}")
        except Exception as e:
            logger.error(f"Error verifying Redis data for {symbol}: {e}")
        
        return price_history
        
    def get_latest_price_history(self, symbol: str) -> Optional[PriceHistory]:
        """
        Get the latest price history data for a symbol from Redis
        """
        redis_key = f"price_history:{symbol}"
        data = redis_client.get_json(redis_key)
        if data:
            # Convert dict back to PriceHistory
            return PriceHistory(**data)
        else:
            logger.warning(f"No price history found for {symbol}")
            return None

    def fetch_polygon_data(self, symbol: str) -> bool:
        """
        Fetch stock market data from Polygon.io for a symbol
        
        Args:
            symbol: Stock ticker symbol (e.g., AAPL, TSLA)
            
        Returns:
            True if data was fetched successfully, False otherwise
        """
        if not self.use_polygon:
            logger.debug(f"Polygon.io API is not configured, skipping data fetch for {symbol}")
            return False
            
        try:
            # Generate a unique request ID for this data
            request_id = str(uuid.uuid4())
            
            # Get the aggregate bars (price data)
            logger.debug(f"Fetching Polygon.io aggregate bars for {symbol}")
            bars = self.polygon_client.get_aggregate_bars(
                symbol=symbol,
                multiplier=1,
                timespan="day",
                limit=10
            )
            
            if not bars:
                logger.warning(f"No Polygon.io aggregate bars data available for {symbol}")
                return False
                
            # Store the data in Redis with a unique key
            polygon_data_key = f"polygon:bars:{symbol}"
            redis_client.set_json(polygon_data_key, {
                "symbol": symbol,
                "data": bars,
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            })
            
            logger.info(f"Successfully stored Polygon.io data for {symbol} with request ID {request_id}")
            
            # Try to get previous close data as well
            prev_close = self.polygon_client.get_previous_close(symbol)
            if prev_close:
                prev_close_key = f"polygon:prev_close:{symbol}"
                redis_client.set_json(prev_close_key, {
                    "symbol": symbol,
                    "data": prev_close,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                })
                logger.debug(f"Stored previous close data for {symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error fetching Polygon.io data for {symbol}: {str(e)}")
            return False
    
    def get_latest_polygon_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest Polygon.io data for a symbol from Redis
        
        Args:
            symbol: Stock ticker symbol (e.g., AAPL, TSLA)
            
        Returns:
            Dictionary containing Polygon.io data or None if not available
        """
        polygon_data_key = f"polygon:bars:{symbol}"
        data = redis_client.get_json(polygon_data_key)
        
        if not data:
            logger.debug(f"No Polygon.io data found in Redis for {symbol}")
            return None
            
        # Check if data is older than 24 hours
        timestamp = datetime.fromisoformat(data.get("timestamp", ""))
        age_seconds = (datetime.now() - timestamp).total_seconds()
        
        if age_seconds > 86400:  # 24 hours
            logger.warning(f"Polygon.io data for {symbol} is older than 24 hours ({age_seconds/3600:.1f} hours)")
            
        return data

# Singleton instance
data_retrieval_service = DataRetrievalService()

# Add this for module execution
if __name__ == "__main__":
    logger.info("Starting Data Retrieval Service as standalone")
    data_retrieval_service.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Data Retrieval Service")
        data_retrieval_service.stop()