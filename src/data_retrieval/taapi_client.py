import requests
import re
import pytz
from typing import Dict, Any, Optional, List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, time

from src.config import config
from src.utils import get_logger, RSIData, MarketStatus

logger = get_logger("taapi_client")

class TaapiClient:
    def __init__(self):
        self.api_key = config.taapi.api_key
        self.base_url = "https://api.taapi.io"
        self.rsi_period = config.taapi.rsi_period
        
        # Stock symbols need to be in specific format for TAAPI
        self.crypto_exchange = "binance"
        self.stock_exchange = "NYSE"
        
        # Define patterns to identify symbol types
        self.crypto_pattern = re.compile(r'[A-Z0-9]+/[A-Z0-9]+')  # Pattern for crypto pairs like BTC/USDT
        self.stock_pattern = re.compile(r'^[A-Z]{1,5}$')  # Pattern for stock tickers like AAPL, TSLA
        
        # US Eastern timezone for market hours
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Regular market hours (9:30 AM - 4:00 PM Eastern)
        self.market_open_time = time(9, 30)
        self.market_close_time = time(16, 0)
        
        # Extended hours
        self.pre_market_open_time = time(4, 0)  # 4:00 AM Eastern
        self.after_hours_close_time = time(20, 0)  # 8:00 PM Eastern
        
        if not self.api_key:
            logger.error("TAAPI API key is not set")
            raise ValueError("TAAPI API key is not set")
            
        logger.debug(f"Using TAAPI API key: {self.api_key[:10]}...{self.api_key[-10:]}")
        
    def _get_market_status(self, symbol: str) -> MarketStatus:
        """
        Determine the current market status for a stock symbol
        
        Args:
            symbol: Stock symbol to check
            
        Returns:
            MarketStatus enum indicating current trading status
        """
        # Cryptocurrencies trade 24/7
        if self.crypto_pattern.match(symbol):
            return MarketStatus.OPEN
            
        # For stocks, check current time in Eastern timezone
        now = datetime.now(self.eastern_tz)
        current_time = now.time()
        current_weekday = now.weekday()
        
        # Check if it's a weekend (5=Saturday, 6=Sunday)
        if current_weekday >= 5:
            return MarketStatus.CLOSED
            
        # Check if within regular market hours (9:30 AM - 4:00 PM Eastern)
        if self.market_open_time <= current_time <= self.market_close_time:
            return MarketStatus.OPEN
            
        # Check if it's pre-market (4:00 AM - 9:30 AM Eastern)
        elif self.pre_market_open_time <= current_time < self.market_open_time:
            return MarketStatus.PRE_MARKET
            
        # Check if it's after-hours (4:00 PM - 8:00 PM Eastern)
        elif self.market_close_time < current_time <= self.after_hours_close_time:
            return MarketStatus.AFTER_HOURS
            
        # Outside of all trading hours
        else:
            return MarketStatus.CLOSED
            
    def _normalize_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Normalize symbol for TAAPI API and determine the correct exchange.
        
        Returns:
            Tuple containing (normalized_symbol, exchange)
        """
        # If it already has a slash, it's likely a crypto pair
        if self.crypto_pattern.match(symbol):
            logger.debug(f"Symbol {symbol} recognized as cryptocurrency pair")
            return symbol, self.crypto_exchange
            
        # If it matches our stock pattern, format it for stocks
        elif self.stock_pattern.match(symbol):
            # For stocks, TAAPI expects them in format SYMBOL/USD
            # Pro tier supports stock symbols, while free tier is limited to specific crypto pairs
            normalized = f"{symbol}/USD"
            logger.debug(f"Symbol {symbol} converted to stock format: {normalized}")
            return normalized, self.stock_exchange
            
        # Default case - just pass through and use crypto exchange
        logger.warning(f"Symbol {symbol} doesn't match known patterns, treating as crypto")
        return symbol, self.crypto_exchange
    
    @retry(
        stop=stop_after_attempt(5),  # Increased from 3 to 5 attempts
        wait=wait_exponential(multiplier=1, min=2, max=15),  # Longer max wait time
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_rsi(self, symbol: str, interval: str = "1m") -> Optional[RSIData]:
        """
        Fetch RSI data for a given symbol from TAAPI.io
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT) or stock symbol (e.g., TSLA)
            interval: Time interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
            
        Returns:
            RSIData object or None if request fails
        """
        # Normalize the symbol and get appropriate exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        # Build parameters for the request
        params = {
            "secret": self.api_key,
            "exchange": exchange,
            "symbol": normalized_symbol,
            "interval": interval,
            "period": self.rsi_period
        }
        
        logger.info(f"Making TAAPI request for {symbol} (normalized to {normalized_symbol} on {exchange})")
        logger.debug(f"Request params: {params}")
        
        try:
            # Set appropriate timeout based on symbol type (longer for stocks)
            timeout = 60 if exchange == self.stock_exchange else 30
            logger.debug(f"Using timeout of {timeout}s for {symbol} ({exchange})")
            response = requests.get(f"{self.base_url}/rsi", params=params, timeout=timeout)
            
            # Handle error responses before raising for status
            if response.status_code != 200:
                try:
                    error_data = response.json() if response.text else {"errors": ["Unknown error"]}
                except ValueError:  # Includes JSONDecodeError
                    error_data = {"errors": [f"Invalid JSON response: {response.text}"]}
                
                if "errors" in error_data:
                    error_message = "; ".join(error_data["errors"])
                    if "Free plans only permits" in error_message:
                        logger.error(f"Free plan limitation for {symbol}: {error_message}")
                        logger.error("Make sure you're using one of the allowed symbols: [BTC/USDT,ETH/USDT,XRP/USDT,LTC/USDT,XMR/USDT]")
                    else:
                        logger.error(f"API error for {symbol}: {error_message}")
                    return None
            
            response.raise_for_status()
            
            # Check if the response is empty
            if not response.text:
                logger.error(f"Empty response from TAAPI for {symbol}")
                return None
                
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from TAAPI for {symbol}: {e}")
                logger.error(f"Response text: '{response.text}'")
                return None
            
            if "value" in data:
                logger.info(f"Received RSI data for {symbol}: {data['value']}")
                return RSIData(
                    symbol=symbol,  # Keep original symbol in the data
                    value=float(data["value"]),
                    timestamp=datetime.now()
                )
            else:
                logger.error(f"Invalid response from TAAPI for {symbol}: {data}")
                return None
                
        except requests.Timeout as e:
            if exchange == self.stock_exchange:
                logger.error(f"Timeout fetching RSI data for stock symbol {symbol}: {e}")
                logger.warning(f"Stock symbols may require TAAPI Pro tier. Consider removing {symbol} if using free tier.")
            else:
                logger.error(f"Timeout fetching RSI data for {symbol}: {e}")
            # Don't raise the exception, just return None to avoid stopping the whole process
            return None
        except requests.RequestException as e:
            logger.error(f"Error fetching RSI data for {symbol}: {e}")
            # Don't raise the exception, just return None to avoid stopping the whole process
            return None
            
    def get_price(self, symbol: str, interval: str = "1m") -> Optional[Dict[str, Any]]:
        """
        Fetch current price data for a given symbol from TAAPI.io
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT) or stock symbol (e.g., TSLA)
            interval: Time interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
            
        Returns:
            Price data or None if request fails
        """
        # Normalize the symbol and get appropriate exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        params = {
            "secret": self.api_key,
            "exchange": exchange,
            "symbol": normalized_symbol,
            "interval": interval
        }
        
        logger.debug(f"Making TAAPI price request for {symbol} (normalized to {normalized_symbol})")
        
        try:
            # Set appropriate timeout based on symbol type (longer for stocks)
            timeout = 60 if exchange == self.stock_exchange else 30
            logger.debug(f"Using timeout of {timeout}s for price request ({symbol})")
            response = requests.get(f"{self.base_url}/candle", params=params, timeout=timeout)
            
            if response.status_code != 200:
                try:
                    error_data = response.json() if response.text else {"errors": ["Unknown error"]}
                except ValueError:  # Includes JSONDecodeError
                    error_data = {"errors": [f"Invalid JSON response: {response.text}"]}
                
                if "errors" in error_data:
                    error_message = "; ".join(error_data["errors"])
                    logger.error(f"API error for {symbol} price data: {error_message}")
                return None
            
            response.raise_for_status()
            
            # Check if the response is empty
            if not response.text:
                logger.error(f"Empty response from TAAPI for {symbol} price data")
                return None
                
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from TAAPI for {symbol} price data: {e}")
                logger.error(f"Response text: '{response.text}'")
                return None
            
            logger.info(f"Received price data for {symbol}: {data['close']}")
            return data
                
        except requests.Timeout as e:
            if exchange == self.stock_exchange:
                logger.error(f"Timeout fetching price data for stock symbol {symbol}: {e}")
                logger.warning(f"Stock symbols may require TAAPI Pro tier. Consider removing {symbol} if using free tier.")
            else:
                logger.error(f"Timeout fetching price data for {symbol}: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
            return None

    def get_price_history(self, symbol: str, interval: str = "5m", limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch historical price data for a given symbol from TAAPI.io
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT) or stock symbol (e.g., TSLA)
            interval: Time interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to retrieve
            
        Returns:
            List of historical price data or None if request fails
        """
        # Normalize the symbol and get appropriate exchange
        normalized_symbol, exchange = self._normalize_symbol(symbol)
        
        params = {
            "secret": self.api_key,
            "exchange": exchange,
            "symbol": normalized_symbol,
            "interval": interval,
            "limit": limit
        }
        
        logger.debug(f"Making TAAPI historical price request for {symbol} (normalized to {normalized_symbol})")
        
        try:
            # Set appropriate timeout based on symbol type (longer for stocks)
            timeout = 60 if exchange == self.stock_exchange else 30
            logger.debug(f"Using timeout of {timeout}s for historical price request ({symbol})")
            response = requests.get(f"{self.base_url}/candles", params=params, timeout=timeout)
            
            if response.status_code != 200:
                try:
                    error_data = response.json() if response.text else {"errors": ["Unknown error"]}
                except ValueError:  # Includes JSONDecodeError
                    error_data = {"errors": [f"Invalid JSON response: {response.text}"]}
                
                if "errors" in error_data:
                    error_message = "; ".join(error_data["errors"])
                    logger.error(f"API error for {symbol} historical price data: {error_message}")
                return None
            
            response.raise_for_status()
            
            # Check if the response is empty
            if not response.text:
                logger.error(f"Empty response from TAAPI for {symbol} historical price data")
                return None
                
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from TAAPI for {symbol} historical price data: {e}")
                logger.error(f"Response text: '{response.text}'")
                return None
            
            logger.info(f"Received historical price data for {symbol}: {len(data)} candles")
            return data
                
        except requests.Timeout as e:
            if exchange == self.stock_exchange:
                logger.error(f"Timeout fetching historical price data for stock symbol {symbol}: {e}")
                logger.warning(f"Stock symbols may require TAAPI Pro tier. Consider removing {symbol} if using free tier.")
            else:
                logger.error(f"Timeout fetching historical price data for {symbol}: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Error fetching historical price data for {symbol}: {e}")
            return None

taapi_client = TaapiClient()