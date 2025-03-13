import os
import time
import re
import logging
import requests
import random
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time as dt_time, timedelta
import pytz
import json

from src.utils import get_logger, RSIData, PriceHistory, PriceCandle, MarketStatus
from src.config import config

logger = get_logger("taapi_client")

class TaapiClient:
    def __init__(self):
        self.api_key = config.taapi.api_key
        self.rsi_period = config.taapi.rsi_period
        self.base_url = "https://api.taapi.io"
        self.last_request_time = 0
        self.min_request_interval = 16  # Minimum time between requests in seconds for free tier
        self.retry_count = 0
        self.max_retries = 3
        self.backoff_factor = 2  # Exponential backoff factor
        
        # Regular expression to detect cryptocurrency symbols like "BTC/USD"
        self.crypto_pattern = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+$")
        
        # Set up timezone for market hours checking
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Normal market hours (9:30 AM - 4:00 PM Eastern)
        self.market_open_time = dt_time(9, 30)
        self.market_close_time = dt_time(16, 0)
        
        # Extended hours
        self.pre_market_open_time = dt_time(4, 0)  # 4:00 AM Eastern
        self.after_hours_close_time = dt_time(20, 0)  # 8:00 PM Eastern
        
        logger.info(f"TAAPI client initialized with key prefix: {self.api_key[:5]}... and RSI period: {self.rsi_period}")
    
    def _normalize_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Normalize the symbol format for TAAPI API
        
        For crypto: Use as-is with binance exchange, but convert BTC/USD to BTC/USDT
        For stocks: Use symbol directly with type=stocks parameter
            
        Returns:
            Tuple of (normalized_symbol, exchange)
        """
        # Check if this is a crypto symbol (contains '/')
        if self.crypto_pattern.match(symbol):
            # For crypto, use the symbol as-is and binance as exchange
            # But convert USD to USDT as TAAPI uses USDT pairs
            if symbol.endswith('/USD'):
                normalized_symbol = symbol.replace('/USD', '/USDT')
                logger.info(f"Converting {symbol} to {normalized_symbol} for TAAPI API")
                return normalized_symbol, "binance"
            return symbol, "binance"
        else:
            # For stocks, return the symbol as-is and None for exchange
            # The API will use the type=stocks parameter instead
            return symbol, None
            
    def _wait_for_rate_limit(self):
        """
        Wait if needed to respect API rate limits
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            # Calculate wait time with jitter to avoid request alignment
            wait_time = self.min_request_interval - time_since_last_request
            jitter = random.uniform(0, 2)  # Add random jitter between 0-2 seconds
            wait_time += jitter
            logger.debug(f"Rate limiting: Waiting {wait_time:.2f} seconds before next request")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def _handle_rate_limit(self, response):
        """
        Handle rate limit response with exponential backoff
        
        Returns:
            True if should retry, False if max retries exceeded
        """
        if response.status_code == 429:  # Too Many Requests
            self.retry_count += 1
            if self.retry_count <= self.max_retries:
                # Calculate backoff time
                backoff_time = self.min_request_interval * (self.backoff_factor ** self.retry_count)
                # Add jitter
                backoff_time += random.uniform(1, 5)
                logger.warning(f"Rate limited (429). Retry {self.retry_count}/{self.max_retries} after {backoff_time:.1f}s")
                time.sleep(backoff_time)
                return True
            else:
                logger.error(f"Max retries ({self.max_retries}) exceeded for rate limit")
                return False
        return False
        
    def get_rsi(self, symbol: str, interval: str = "1m") -> Optional[RSIData]:
        """
        Get the current RSI value for a symbol
        
        Args:
            symbol: Trading symbol (e.g., BTC/USD or AAPL)
            interval: Time interval (default: 1m - 1 minute)
            
        Returns:
            RSIData object or None if error
        """
        # Normalize symbol and get exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        # Determine if this is a stock symbol
        is_stock = not self.crypto_pattern.match(symbol)
        
        if is_stock:
            logger.info(f"Making TAAPI request for stock {symbol}")
        else:
            logger.info(f"Making TAAPI request for {symbol} (normalized to {normalized_symbol} on {exchange})")
        
        # Check if API key is configured
        if not self.api_key:
            logger.error("TAAPI API key not configured")
            return None
            
        # Wait to respect rate limits
        self._wait_for_rate_limit()
        
        # Reset retry counter for new request
        self.retry_count = 0
        
        # Prepare API parameters
        params = {
            "secret": self.api_key,
            "symbol": normalized_symbol,
            "interval": interval,
            "period": self.rsi_period
        }
        
        # Add exchange parameter for crypto symbols
        if exchange:
            params["exchange"] = exchange
        
        # Add type parameter for stock symbols
        if is_stock:
            params["type"] = "stocks"
        
        # Make the request with retry logic
        while self.retry_count <= self.max_retries:
            try:
                response = requests.get(f"{self.base_url}/rsi", params=params, timeout=10)
                
                # Handle successful response
                if response.status_code == 200:
                    data = response.json()
                    rsi_value = data.get("value")
                    
                    if rsi_value is not None:
                        # Create RSI data object
                        rsi_data = RSIData(
                            symbol=symbol,
                            value=float(rsi_value),
                            interval=interval,
                            timestamp=datetime.now()
                        )
                        logger.info(f"Got RSI value for {symbol}: {rsi_value}")
                        return rsi_data
                    else:
                        logger.error(f"No RSI value in response for {symbol}")
                        return None
                
                # Handle rate limiting
                elif response.status_code == 429:
                    if self._handle_rate_limit(response):
                        continue  # Retry after backoff
                    else:
                        return None  # Max retries exceeded
                
                # Handle API errors
                elif response.status_code >= 400:
                    try:
                        error_msg = response.json().get('message', f'HTTP error {response.status_code}')
                    except:
                        error_msg = f'HTTP error {response.status_code}'
                        
                    logger.error(f"API error for {symbol}: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching RSI data for {symbol}: {e}")
                
                # Retry on connection errors
                self.retry_count += 1
                if self.retry_count <= self.max_retries:
                    backoff_time = 2 ** self.retry_count
                    logger.info(f"Retrying in {backoff_time} seconds... (attempt {self.retry_count}/{self.max_retries})")
                    time.sleep(backoff_time)
                    continue
                return None
                
            # If we got here without continuing the loop, break
            break
                
        return None

    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the current price data for a symbol
        
        Args:
            symbol: Trading symbol (e.g., BTC/USD or AAPL)
            
        Returns:
            Dictionary with price data or None if error
        """
        # Normalize symbol and get exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        # Determine if this is a stock symbol
        is_stock = not self.crypto_pattern.match(symbol)
        
        # Check if API key is configured
        if not self.api_key:
            logger.error("TAAPI API key not configured")
            return None
            
        # Wait to respect rate limits
        self._wait_for_rate_limit()
        
        # Reset retry counter for new request
        self.retry_count = 0
        
        # Prepare API parameters
        params = {
            "secret": self.api_key,
            "symbol": normalized_symbol,
            "interval": "1m"  # Use 1-minute interval for current price
        }
        
        # Add exchange parameter for crypto symbols
        if exchange:
            params["exchange"] = exchange
        
        # Add type parameter for stock symbols
        if is_stock:
            params["type"] = "stocks"
        
        # Make the request with retry logic
        while self.retry_count <= self.max_retries:
            try:
                response = requests.get(f"{self.base_url}/candle", params=params, timeout=10)
                
                # Handle successful response
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "symbol": symbol,
                        "timestamp": datetime.now().isoformat(),
                        "open": data.get("open"),
                        "high": data.get("high"),
                        "low": data.get("low"),
                        "close": data.get("close"),
                        "volume": data.get("volume", 0)
                    }
                
                # Handle rate limiting
                elif response.status_code == 429:
                    if self._handle_rate_limit(response):
                        continue  # Retry after backoff
                    else:
                        return None  # Max retries exceeded
                
                # Handle other errors
                else:
                    try:
                        error_msg = response.json().get('message', f'HTTP error {response.status_code}')
                    except:
                        error_msg = f'HTTP error {response.status_code}'
                        
                    logger.error(f"API error for price data - {symbol}: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching price data for {symbol}: {str(e)}")
                
                # Retry on connection errors
                self.retry_count += 1
                if self.retry_count <= self.max_retries:
                    backoff_time = 2 ** self.retry_count
                    logger.info(f"Retrying in {backoff_time} seconds... (attempt {self.retry_count}/{self.max_retries})")
                    time.sleep(backoff_time)
                    continue
                return None
                
            # If we got here without continuing the loop, break
            break
            
        return None
        
    def get_price_history(self, symbol: str, interval: str = "1h", limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical price data for a symbol
        
        Args:
            symbol: Trading symbol (e.g., BTC/USD or AAPL)
            interval: Time interval (default: 1h - 1 hour)
            limit: Number of candles to return (default: 20)
            
        Returns:
            List of candle data or None if error
        """
        # Normalize symbol and get exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        # Determine if this is a stock symbol
        is_stock = not self.crypto_pattern.match(symbol)
        
        # Check if API key is configured
        if not self.api_key:
            logger.error("TAAPI API key not configured")
            return None
            
        # Wait to respect rate limits
        self._wait_for_rate_limit()
        
        # Reset retry counter for new request
        self.retry_count = 0
        
        # Prepare API parameters
        params = {
            "secret": self.api_key,
            "symbol": normalized_symbol,
            "interval": interval,
            "limit": limit
        }
        
        # Add exchange parameter for crypto symbols
        if exchange:
            params["exchange"] = exchange
        
        # Add type parameter for stock symbols
        if is_stock:
            params["type"] = "stocks"
        
        # Make the request with retry logic
        while self.retry_count <= self.max_retries:
            try:
                response = requests.get(f"{self.base_url}/bulk/candles", params=params, timeout=15)
                
                # Handle successful response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Process all candles
                        candles = []
                        for candle in data:
                            # Add timestamp to each candle
                            timestamp = candle.get("timestampHuman")
                            if timestamp:
                                # Convert to timestamp integer
                                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                                candle["timestamp"] = int(dt.timestamp())
                            
                            candles.append(candle)
                            
                        logger.info(f"Got {len(candles)} historical candles for {symbol}")
                        return candles
                    except (ValueError, KeyError) as e:
                        logger.error(f"Error parsing historical price data for {symbol}: {str(e)}")
                        return None
                
                # Handle rate limiting
                elif response.status_code == 429:
                    if self._handle_rate_limit(response):
                        continue  # Retry after backoff
                    else:
                        return None  # Max retries exceeded
                
                # Handle other errors
                else:
                    try:
                        error_msg = response.json().get('message', f'HTTP error {response.status_code}')
                    except:
                        error_msg = f'HTTP error {response.status_code}'
                        
                    logger.error(f"API error for {symbol} historical price data: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching historical price data for {symbol}: {str(e)}")
                
                # Retry on connection errors
                self.retry_count += 1
                if self.retry_count <= self.max_retries:
                    backoff_time = 2 ** self.retry_count
                    logger.info(f"Retrying in {backoff_time} seconds... (attempt {self.retry_count}/{self.max_retries})")
                    time.sleep(backoff_time)
                    continue
                return None
                
            # If we got here without continuing the loop, break
            break
            
        return None

# Singleton instance
taapi_client = TaapiClient()