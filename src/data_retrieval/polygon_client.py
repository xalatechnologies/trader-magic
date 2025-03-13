"""
Polygon.io client for retrieving stock market data.
"""

import requests
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, date
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import config
from src.utils import get_logger, TradeSignal, TradingDecision

logger = get_logger("polygon_client")

class PolygonClient:
    """
    Client for interacting with the Polygon.io API to retrieve stock market data.
    """
    
    def __init__(self):
        """Initialize the Polygon.io client with API key from config."""
        self.api_key = config.polygon.api_key
        self.base_url = "https://api.polygon.io"
        
        if not self.api_key:
            logger.error("Polygon.io API key is not set")
            raise ValueError("Polygon.io API key is not set")
            
        logger.debug(f"Using Polygon.io API key: {self.api_key[:5]}...{self.api_key[-5:]}")
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_ticker_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a ticker.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            
        Returns:
            Dictionary containing ticker details or None if error
        """
        endpoint = f"/v3/reference/tickers/{symbol}"
        params = {
            "apiKey": self.api_key
        }
        
        try:
            logger.debug(f"Fetching ticker details for {symbol}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Successfully retrieved ticker details for {symbol}")
                return data.get("results")
            else:
                logger.error(f"Failed to get ticker details for {symbol}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting ticker details for {symbol}: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_ticker_news(self, symbol: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get latest news for a ticker.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            limit: Maximum number of news items to retrieve
            
        Returns:
            List of news items or None if error
        """
        endpoint = f"/v2/reference/news"
        params = {
            "ticker": symbol,
            "limit": limit,
            "apiKey": self.api_key
        }
        
        try:
            logger.debug(f"Fetching news for {symbol}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Successfully retrieved {len(data.get('results', []))} news items for {symbol}")
                return data.get("results", [])
            else:
                logger.error(f"Failed to get news for {symbol}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting news for {symbol}: {str(e)}")
            raise
    
    def get_latest_news_with_sentiment(self, symbol: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Get latest news items with sentiment analysis.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            limit: Maximum number of news items to retrieve
            
        Returns:
            List of news items with sentiment scores or None if error
        """
        news_items = self.get_ticker_news(symbol, limit)
        if not news_items:
            logger.warning(f"No news items found for {symbol}")
            return None
        
        # Check if OpenAI API key is configured
        if not config.openai.api_key:
            logger.warning("OpenAI API key not set, cannot analyze news sentiment")
            return news_items
        
        try:
            from src.utils.sentiment_analyzer import analyze_sentiment
            
            # Process each news item for sentiment
            for item in news_items:
                headline = item.get('headline', '')
                description = item.get('description', '')
                
                # Combine headline and description for analysis
                content = f"{headline}. {description}"
                
                # Analyze sentiment
                sentiment_result = analyze_sentiment(content)
                
                # Add sentiment data to the news item
                item['sentiment'] = sentiment_result.get('sentiment', 'neutral')
                item['sentiment_score'] = sentiment_result.get('score', 50)
                
            logger.info(f"Analyzed sentiment for {len(news_items)} news items for {symbol}")
            return news_items
            
        except Exception as e:
            logger.error(f"Error analyzing news sentiment for {symbol}: {str(e)}")
            # Return the original news items without sentiment
            return news_items
    
    def generate_news_signal(self, symbol: str, news_items: Optional[List[Dict[str, Any]]] = None) -> Optional[TradeSignal]:
        """
        Generate a trading signal based on news sentiment analysis.
        
        Args:
            symbol: The stock ticker symbol
            news_items: List of news items with sentiment or None to fetch
            
        Returns:
            TradeSignal object or None if no signal is generated
        """
        # Fetch news if not provided
        if news_items is None:
            news_items = self.get_latest_news_with_sentiment(symbol)
            
        if not news_items:
            logger.debug(f"No news items available for {symbol} to generate signal")
            return None
            
        # Calculate average sentiment score
        sentiment_scores = [item.get('sentiment_score', 50) for item in news_items 
                            if 'sentiment_score' in item]
        
        if not sentiment_scores:
            logger.debug(f"No sentiment scores available for {symbol}")
            return None
            
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        
        # Define thresholds for trading decisions
        buy_threshold = 70  # Bullish sentiment
        sell_threshold = 30  # Bearish sentiment
        
        decision = TradingDecision.HOLD
        confidence = 0.5
        
        if avg_sentiment >= buy_threshold:
            decision = TradingDecision.BUY
            # Scale confidence based on how strong the sentiment is
            confidence = min(0.9, 0.5 + ((avg_sentiment - buy_threshold) / 60))
            logger.info(f"BUY signal for {symbol} based on news sentiment: {avg_sentiment:.1f}, confidence: {confidence:.2f}")
            
        elif avg_sentiment <= sell_threshold:
            decision = TradingDecision.SELL
            # Scale confidence based on how negative the sentiment is
            confidence = min(0.9, 0.5 + ((sell_threshold - avg_sentiment) / 60))
            logger.info(f"SELL signal for {symbol} based on news sentiment: {avg_sentiment:.1f}, confidence: {confidence:.2f}")
            
        else:
            # Sentiment is neutral, no clear signal
            logger.debug(f"HOLD for {symbol} based on neutral news sentiment: {avg_sentiment:.1f}")
            return None
            
        # Create metadata with headlines and sentiment
        headlines = [item.get('headline', 'No headline') for item in news_items[:3]]
        
        # Create the trade signal
        return TradeSignal(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            timestamp=datetime.now(),
            metadata={
                "avg_sentiment": avg_sentiment,
                "num_articles": len(news_items),
                "headlines": headlines,
                "data_source": "polygon.io_news"
            }
        )
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_daily_open_close(self, symbol: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Get daily open/close data for a ticker on a specific date.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            date: The date in format YYYY-MM-DD
            
        Returns:
            Dictionary with open, close, high, low prices or None if error
        """
        endpoint = f"/v1/open-close/{symbol}/{date}"
        params = {
            "adjusted": "true",
            "apiKey": self.api_key
        }
        
        try:
            logger.debug(f"Fetching daily open/close for {symbol} on {date}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Successfully retrieved daily data for {symbol} on {date}")
                return data
            else:
                logger.error(f"Failed to get daily data for {symbol} on {date}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting daily data for {symbol} on {date}: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_aggregate_bars(self, symbol: str, multiplier: int = 1, timespan: str = "day", 
                         from_date: str = None, to_date: str = None, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get aggregate bars for a ticker over a given date range in custom time window sizes.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            multiplier: The size of the timespan multiplier
            timespan: The size of the time window (minute, hour, day, week, month, quarter, year)
            from_date: The start date in format YYYY-MM-DD
            to_date: The end date in format YYYY-MM-DD
            limit: Maximum number of bars to retrieve
            
        Returns:
            List of price bars or None if error
        """
        # Set default dates if not provided
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
            
        endpoint = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {
            "adjusted": "true",
            "sort": "desc",
            "limit": limit,
            "apiKey": self.api_key
        }
        
        try:
            logger.debug(f"Fetching aggregate bars for {symbol} from {from_date} to {to_date}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Successfully retrieved {len(data.get('results', []))} bars for {symbol}")
                return data.get("results", [])
            else:
                logger.error(f"Failed to get aggregate bars for {symbol}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting aggregate bars for {symbol}: {str(e)}")
            raise
    
    def get_historical_data_for_backtest(self, symbol: str, start_date: str, end_date: str, 
                                        timespan: str = "day", multiplier: int = 1) -> Optional[List[Dict[str, Any]]]:
        """
        Get comprehensive historical data for backtesting strategies.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timespan: Time window (minute, hour, day, week, month)
            multiplier: Multiplier for the timespan
            
        Returns:
            List of OHLCV bars for the specified period or None if error
        """
        # Validate date formats
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            logger.error(f"Invalid date format: {str(e)}")
            return None
        
        # Calculate date periods for fetching data
        # Polygon has limits on how much data can be retrieved at once,
        # so we may need to make multiple requests
        
        # For daily data, we can request up to 5000 bars
        # For minute data, we may need to chunk by days or weeks
        data_chunks = []
        
        try:
            # For day, week, month timeframes - we can fetch all at once
            if timespan in ["day", "week", "month"]:
                return self.get_aggregate_bars(
                    symbol=symbol,
                    multiplier=multiplier,
                    timespan=timespan,
                    from_date=start_date,
                    to_date=end_date,
                    limit=5000  # Request maximum allowed
                )
            
            # For minute/hour data, we need to break it into smaller chunks
            elif timespan in ["minute", "hour"]:
                # Convert dates to datetime objects
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                # For minute/hour data, chunk by weeks or months depending on the range
                chunk_size = timedelta(days=7)  # Default to 7-day chunks
                
                # If the range is large, use monthly chunks for efficiency
                if (end_dt - start_dt).days > 90:
                    chunk_size = timedelta(days=30)
                
                # Fetch data in chunks
                current_start = start_dt
                while current_start < end_dt:
                    current_end = min(current_start + chunk_size, end_dt)
                    
                    # Format dates for API call
                    chunk_start = current_start.strftime("%Y-%m-%d")
                    chunk_end = current_end.strftime("%Y-%m-%d")
                    
                    # Get data for this chunk
                    chunk_data = self.get_aggregate_bars(
                        symbol=symbol,
                        multiplier=multiplier,
                        timespan=timespan,
                        from_date=chunk_start,
                        to_date=chunk_end,
                        limit=50000  # High limit for intraday data
                    )
                    
                    # Add results to the combined list
                    if chunk_data:
                        data_chunks.extend(chunk_data)
                        logger.info(f"Retrieved {len(chunk_data)} bars for {symbol} from {chunk_start} to {chunk_end}")
                    
                    # Move to the next chunk
                    current_start = current_end + timedelta(days=1)
                    
                    # Add a small delay to avoid hitting rate limits
                    time.sleep(0.5)
                
                logger.info(f"Retrieved a total of {len(data_chunks)} bars for {symbol} from {start_date} to {end_date}")
                return data_chunks
                
            else:
                logger.error(f"Unsupported timespan: {timespan}. Use minute, hour, day, week, or month.")
                return None
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return None
    
    def run_backtest(self, symbol: str, strategy_function, start_date: str, end_date: str, 
                    timespan: str = "day", initial_capital: float = 10000.0) -> Dict[str, Any]:
        """
        Run a backtest for a given strategy on historical data.
        
        Args:
            symbol: The stock ticker symbol
            strategy_function: Function that takes price data and returns a trading decision
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            timespan: Time window (day, hour, minute)
            initial_capital: Starting capital amount
            
        Returns:
            Dictionary with backtest results
        """
        # Fetch historical data
        historical_data = self.get_historical_data_for_backtest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timespan=timespan
        )
        
        if not historical_data:
            logger.error(f"No historical data available for {symbol} from {start_date} to {end_date}")
            return {
                "success": False,
                "error": "No historical data available"
            }
            
        # Ensure data is in chronological order (oldest first)
        data = sorted(historical_data, key=lambda x: x['t'])
        
        # Initialize backtest variables
        capital = initial_capital
        position = 0  # Number of shares held
        trades = []
        portfolio_values = []
        
        # Run the backtest
        for i in range(len(data)):
            # Skip first few bars if we need them for indicators
            if i < 20:  # Skip first 20 bars for indicator calculation
                portfolio_values.append({
                    "date": datetime.fromtimestamp(data[i]['t'] / 1000).strftime("%Y-%m-%d"),
                    "value": capital,
                    "price": data[i]['c']
                })
                continue
                
            # Get current bar
            current_bar = data[i]
            
            # Get the relevant historical data for the strategy
            # (current bar and N previous bars)
            historical_window = list(reversed(data[max(0, i-50):i+1]))
            
            # Apply strategy to get a signal
            signal = strategy_function(historical_window)
            
            # Process the signal
            if signal and signal.decision != TradingDecision.HOLD:
                price = current_bar['c']  # Use closing price for simplicity
                
                if signal.decision == TradingDecision.BUY and position == 0:
                    # Calculate position size (number of shares to buy)
                    position_size = capital * 0.95  # Use 95% of capital
                    position = position_size / price
                    capital -= position_size
                    
                    trades.append({
                        "date": datetime.fromtimestamp(current_bar['t'] / 1000).strftime("%Y-%m-%d"),
                        "type": "BUY",
                        "price": price,
                        "shares": position,
                        "value": position_size,
                        "confidence": signal.confidence
                    })
                    
                elif signal.decision == TradingDecision.SELL and position > 0:
                    # Sell entire position
                    sale_value = position * price
                    capital += sale_value
                    
                    trades.append({
                        "date": datetime.fromtimestamp(current_bar['t'] / 1000).strftime("%Y-%m-%d"),
                        "type": "SELL",
                        "price": price,
                        "shares": position,
                        "value": sale_value,
                        "confidence": signal.confidence
                    })
                    
                    position = 0
            
            # Calculate portfolio value
            portfolio_value = capital + (position * current_bar['c'])
            
            portfolio_values.append({
                "date": datetime.fromtimestamp(current_bar['t'] / 1000).strftime("%Y-%m-%d"),
                "value": portfolio_value,
                "price": current_bar['c']
            })
        
        # Calculate final performance metrics
        if not portfolio_values:
            return {
                "success": False,
                "error": "No portfolio values calculated"
            }
        
        initial_value = initial_capital
        final_value = portfolio_values[-1]["value"]
        
        # Calculate returns
        total_return = (final_value - initial_value) / initial_value * 100
        
        # Calculate buy & hold return
        if len(data) > 1:
            buy_hold_return = (data[-1]['c'] - data[0]['c']) / data[0]['c'] * 100
        else:
            buy_hold_return = 0
        
        return {
            "success": True,
            "symbol": symbol,
            "period": f"{start_date} to {end_date}",
            "initial_capital": initial_capital,
            "final_capital": final_value,
            "total_return_pct": total_return,
            "buy_hold_return_pct": buy_hold_return,
            "trades": trades,
            "portfolio_values": portfolio_values
        }
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_previous_close(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the previous day's open, high, low, and close (OHLC) for a ticker.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            
        Returns:
            Dictionary containing previous day's OHLC data or None if error
        """
        endpoint = f"/v2/aggs/ticker/{symbol}/prev"
        params = {
            "adjusted": "true",
            "apiKey": self.api_key
        }
        
        try:
            logger.debug(f"Fetching previous close for {symbol}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results") and len(data.get("results")) > 0:
                    logger.debug(f"Successfully retrieved previous close for {symbol}")
                    return data.get("results")[0]
                else:
                    logger.warning(f"No previous close data available for {symbol}")
                    return None
            else:
                logger.error(f"Failed to get previous close for {symbol}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting previous close for {symbol}: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError, requests.Timeout)),
        reraise=True
    )
    def get_technical_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get common technical indicators for a symbol using Polygon's technical indicators endpoint.
        
        Args:
            symbol: The stock ticker symbol (e.g., AAPL, TSLA)
            
        Returns:
            Dictionary containing technical indicators or None if error
        """
        # This is a premium endpoint, so we'll check for proper subscription
        # and handle accordingly
        indicators = {}
        
        try:
            # Get price data first
            price_data = self.get_aggregate_bars(symbol, timespan="day", limit=50)
            if not price_data or len(price_data) < 50:
                logger.warning(f"Insufficient price data for {symbol} to calculate indicators")
                return None
            
            # Calculate RSI manually
            rsi = self._calculate_rsi(price_data)
            if rsi:
                indicators["rsi"] = rsi
                indicators["rsi_value"] = rsi.get("value")
                
            # Calculate MACD manually
            macd = self._calculate_macd(price_data)
            if macd:
                indicators["macd"] = macd
                indicators["macd_value"] = macd.get("value")
                indicators["macd_signal"] = macd.get("signal")
                indicators["macd_histogram"] = macd.get("histogram")
                
            # Calculate Bollinger Bands
            bollinger = self._calculate_bollinger_bands(price_data)
            if bollinger:
                indicators["bollinger"] = bollinger
                indicators["upper_band"] = bollinger.get("upper")
                indicators["middle_band"] = bollinger.get("middle")
                indicators["lower_band"] = bollinger.get("lower")
            
            logger.info(f"Successfully calculated technical indicators for {symbol}")
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {str(e)}")
            return None
    
    def _calculate_rsi(self, price_data: List[Dict[str, Any]], period: int = 14) -> Optional[Dict[str, Any]]:
        """
        Calculate Relative Strength Index (RSI) from price data
        
        Args:
            price_data: List of price bars
            period: RSI period (default: 14)
            
        Returns:
            Dictionary with RSI values or None if error
        """
        if len(price_data) < period + 1:
            logger.warning(f"Not enough data to calculate RSI (need {period + 1}, got {len(price_data)})")
            return None
            
        try:
            # Extract closing prices in reverse order to get chronological order
            closes = [bar['c'] for bar in reversed(price_data[:period + 1])]
            
            # Calculate price changes
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            
            # Separate gains and losses
            gains = [max(0, change) for change in changes]
            losses = [max(0, -change) for change in changes]
            
            # Calculate average gain and loss
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            
            if avg_loss == 0:
                # No losses, RSI = 100
                rsi = 100
            else:
                # Calculate RS and RSI
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            return {
                "value": rsi,
                "period": period,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            return None
    
    def _calculate_macd(self, price_data: List[Dict[str, Any]], 
                       fast_period: int = 12, slow_period: int = 26, 
                       signal_period: int = 9) -> Optional[Dict[str, Any]]:
        """
        Calculate Moving Average Convergence Divergence (MACD) from price data
        
        Args:
            price_data: List of price bars
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)
            
        Returns:
            Dictionary with MACD values or None if error
        """
        if len(price_data) < slow_period + signal_period:
            logger.warning(f"Not enough data to calculate MACD")
            return None
            
        try:
            # Extract closing prices in reverse order to get chronological order
            closes = [bar['c'] for bar in reversed(price_data)]
            
            # Calculate fast and slow EMAs
            fast_ema = self._calculate_ema(closes, fast_period)
            slow_ema = self._calculate_ema(closes, slow_period)
            
            if not fast_ema or not slow_ema:
                return None
                
            # Calculate MACD line
            macd_line = fast_ema[-1] - slow_ema[-1]
            
            # Calculate all MACD values for signal line
            macd_values = [fast_ema[i] - slow_ema[i] for i in range(max(len(fast_ema), len(slow_ema)))]
            
            # Calculate signal line (EMA of MACD)
            signal_line = self._calculate_ema(macd_values, signal_period)
            
            if not signal_line:
                return None
                
            # MACD histogram
            histogram = macd_line - signal_line[-1]
            
            return {
                "value": macd_line,
                "signal": signal_line[-1],
                "histogram": histogram,
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            return None
    
    def _calculate_ema(self, values: List[float], period: int) -> Optional[List[float]]:
        """
        Calculate Exponential Moving Average (EMA)
        
        Args:
            values: List of values to calculate EMA for
            period: EMA period
            
        Returns:
            List of EMA values or None if error
        """
        if len(values) < period:
            return None
            
        # Calculate multiplier
        multiplier = 2 / (period + 1)
        
        # Calculate first EMA using SMA
        sma = sum(values[:period]) / period
        
        # Calculate EMAs
        emas = [sma]
        
        for i in range(period, len(values)):
            ema = (values[i] - emas[-1]) * multiplier + emas[-1]
            emas.append(ema)
            
        return emas
    
    def _calculate_bollinger_bands(self, price_data: List[Dict[str, Any]], 
                                 period: int = 20, std_dev: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Calculate Bollinger Bands from price data
        
        Args:
            price_data: List of price bars
            period: Bollinger Band period (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
            
        Returns:
            Dictionary with Bollinger Band values or None if error
        """
        if len(price_data) < period:
            logger.warning(f"Not enough data to calculate Bollinger Bands")
            return None
            
        try:
            # Extract closing prices in reverse order
            closes = [bar['c'] for bar in reversed(price_data[:period])]
            
            # Calculate middle band (SMA)
            middle_band = sum(closes) / period
            
            # Calculate standard deviation
            variance = sum([(x - middle_band) ** 2 for x in closes]) / period
            stdev = variance ** 0.5
            
            # Calculate upper and lower bands
            upper_band = middle_band + (std_dev * stdev)
            lower_band = middle_band - (std_dev * stdev)
            
            # Get current price
            current_price = price_data[0]['c']
            
            # Calculate position within bands
            band_width = upper_band - lower_band
            if band_width > 0:
                relative_position = (current_price - lower_band) / band_width
            else:
                relative_position = 0.5
                
            return {
                "upper": upper_band,
                "middle": middle_band,
                "lower": lower_band,
                "width": band_width,
                "relative_position": relative_position,
                "current_price": current_price,
                "period": period,
                "std_dev": std_dev,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            return None
    
    def generate_signal_from_data(self, symbol: str, price_data: List[Dict[str, Any]]) -> Optional[TradeSignal]:
        """
        Generate a trading signal based on price data analysis.
        
        Args:
            symbol: The stock ticker symbol
            price_data: List of price bars from get_aggregate_bars
            
        Returns:
            TradeSignal object or None if no signal is generated
        """
        if not price_data or len(price_data) < 2:
            logger.warning(f"Insufficient price data for {symbol} to generate signal")
            return None
            
        # Get the latest price data
        latest = price_data[0]
        previous = price_data[1]
        
        # Calculate price change percentage
        price_change = (latest['c'] - previous['c']) / previous['c'] * 100
        
        # Trading logic based on price change
        decision = TradingDecision.HOLD
        confidence = 0.5
        
        # Significant price increase may indicate BUY
        if price_change > 2.0:
            decision = TradingDecision.BUY
            confidence = min(0.9, 0.5 + (price_change / 20))  # Scale confidence with price change
            logger.info(f"BUY signal for {symbol}: Price up {price_change:.2f}%, confidence: {confidence:.2f}")
            
        # Significant price decrease may indicate SELL
        elif price_change < -2.0:
            decision = TradingDecision.SELL
            confidence = min(0.9, 0.5 + (abs(price_change) / 20))  # Scale confidence with price change
            logger.info(f"SELL signal for {symbol}: Price down {price_change:.2f}%, confidence: {confidence:.2f}")
            
        else:
            # No clear signal
            logger.debug(f"HOLD for {symbol}: Price change {price_change:.2f}% in neutral range")
            return None  # No trade signal for hold
            
        # Create the trade signal
        return TradeSignal(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            timestamp=datetime.now(),
            metadata={
                "price_change_pct": price_change,
                "current_price": latest['c'],
                "previous_price": previous['c'],
                "volume": latest.get('v', 0)
            }
        ) 