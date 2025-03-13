"""
Polygon.io-based trading strategy implementation.
"""

import math
import statistics
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.utils import TradeSignal, TradingDecision, get_logger
from src.strategies.base_strategy import BaseStrategy
from src.data_retrieval.polygon_client import PolygonClient

logger = get_logger("polygon_strategy")

class PolygonStrategy(BaseStrategy):
    """
    Trading strategy that uses Polygon.io market data to generate trading signals.
    Analyzes price movements, volume patterns, and technical indicators to make trading decisions.
    """
    
    name = "Polygon Market Data Strategy"
    description = "Uses Polygon.io stock market data to make trading decisions"
    
    def __init__(self):
        """Initialize the Polygon.io strategy with default settings"""
        super().__init__()
        # Initialize our own instance of PolygonClient
        self.polygon_client = PolygonClient()
        
        # Default thresholds
        self.price_increase_threshold = 2.0   # Percentage increase to trigger BUY
        self.price_decrease_threshold = -2.0  # Percentage decrease to trigger SELL
        self.volume_increase_factor = 1.5     # Volume increase factor for additional confidence
        
        # Time period for analysis
        self.timespan = "day"                 # Time window (minute, hour, day, week, month)
        self.multiplier = 1                   # Multiplier for the timespan
        self.data_points = 10                 # Number of data points to analyze
        
        # Volume spike detection
        self.volume_spike_threshold = 3.0     # Volume spike factor threshold
        
        # Technical indicators
        self.ma_short_period = 20            # Short moving average period (days)
        self.ma_long_period = 50             # Long moving average period (days)
        
        # RSI settings
        self.rsi_period = 14                 # RSI calculation period
        self.rsi_overbought = 70             # Overbought threshold
        self.rsi_oversold = 30               # Oversold threshold
        self.use_rsi_signals = True          # Whether to use RSI for signal generation
        
        # Risk management
        self.max_risk_per_trade = 1.0        # Maximum risk percentage per trade
        self.volatility_adjustment = True    # Adjust position size based on volatility
        
    def configure(self, config: Dict[str, Any]):
        """
        Configure the strategy parameters
        
        Args:
            config: Configuration dictionary with strategy parameters
        """
        # Update standard parameters if provided
        self.enabled = config.get("enabled", True)
        self.price_increase_threshold = config.get("price_increase_threshold", self.price_increase_threshold)
        self.price_decrease_threshold = config.get("price_decrease_threshold", self.price_decrease_threshold)
        self.volume_increase_factor = config.get("volume_increase_factor", self.volume_increase_factor)
        self.timespan = config.get("timespan", self.timespan)
        self.multiplier = config.get("multiplier", self.multiplier)
        self.data_points = config.get("data_points", self.data_points)
        self.volume_spike_threshold = config.get("volume_spike_threshold", self.volume_spike_threshold)
        self.ma_short_period = config.get("ma_short_period", self.ma_short_period)
        self.ma_long_period = config.get("ma_long_period", self.ma_long_period)
        self.max_risk_per_trade = config.get("max_risk_per_trade", self.max_risk_per_trade)
        self.volatility_adjustment = config.get("volatility_adjustment", self.volatility_adjustment)
        
        # RSI settings
        self.rsi_period = config.get("rsi_period", self.rsi_period)
        self.rsi_overbought = config.get("rsi_overbought", self.rsi_overbought)
        self.rsi_oversold = config.get("rsi_oversold", self.rsi_oversold)
        self.use_rsi_signals = config.get("use_rsi_signals", self.use_rsi_signals)
        
        logger.info(
            f"Polygon Strategy configured with: "
            f"price_increase={self.price_increase_threshold}, "
            f"price_decrease={self.price_decrease_threshold}, "
            f"volume_factor={self.volume_increase_factor}, "
            f"volume_spike={self.volume_spike_threshold}, "
            f"ma_short={self.ma_short_period}, "
            f"ma_long={self.ma_long_period}, "
            f"rsi_period={self.rsi_period}, "
            f"rsi_overbought={self.rsi_overbought}, "
            f"rsi_oversold={self.rsi_oversold}, "
            f"use_rsi={self.use_rsi_signals}"
        )
    
    def process_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process market data and generate trading signals
        
        Args:
            data: Dictionary containing symbol and market data
            
        Returns:
            Trading signal dictionary or None
        """
        if not self.enabled:
            return None
            
        # Extract symbol and check if data is provided
        symbol = data.get("symbol")
        if not symbol:
            logger.warning("No symbol provided in data")
            return None
        
        # Check if we have polygon data in the provided data
        polygon_data = data.get("polygon_data", {})
        price_bars = polygon_data.get("bars", [])
        
        # If we don't have polygon data, try to fetch it
        if not price_bars or len(price_bars) < 2:
            logger.debug(f"Insufficient polygon data for {symbol}, fetching directly")
            try:
                price_bars = self.polygon_client.get_aggregate_bars(
                    symbol, 
                    multiplier=self.multiplier,
                    timespan=self.timespan,
                    limit=max(self.data_points, self.ma_long_period, self.rsi_period + 5)
                )
                if not price_bars or len(price_bars) < 2:
                    logger.warning(f"Insufficient Polygon data available for {symbol}")
                    return None
            except Exception as e:
                logger.error(f"Error fetching Polygon data for {symbol}: {str(e)}")
                return None
        
        # Run comprehensive analysis for signal generation
        return self._generate_comprehensive_signal(symbol, price_bars, data.get("price"))
    
    def _generate_comprehensive_signal(self, symbol: str, price_bars: List[Dict[str, Any]], current_price: float = None) -> Optional[Dict[str, Any]]:
        """
        Generate a comprehensive trading signal using multiple analysis methods
        
        Args:
            symbol: The trading symbol
            price_bars: List of price bars from polygon
            current_price: Current price (optional, will use latest bar close if not provided)
            
        Returns:
            Signal dictionary or None if no signal
        """
        if not price_bars or len(price_bars) < 2:
            logger.warning(f"Not enough price data points for {symbol} to generate signal")
            return None
            
        # Extract the latest and previous price data
        latest_bar = price_bars[0]
        previous_bar = price_bars[1]
        
        # Use provided current price or fall back to latest close
        if current_price is None:
            current_price = latest_bar.get('c')
        
        # Calculate various indicators
        price_change = self._calculate_price_change(latest_bar, previous_bar)
        volume_analysis = self._analyze_volume(price_bars)
        moving_averages = self._calculate_moving_averages(price_bars)
        volatility = self._calculate_volatility(price_bars)
        
        # Calculate RSI
        rsi_data = self._analyze_rsi(price_bars)
        
        # Initialize signal components
        decision = TradingDecision.HOLD
        confidence = 0.5
        signal_reasons = []
        
        # 1. Price Change Analysis
        if price_change > self.price_increase_threshold:
            decision = TradingDecision.BUY
            price_confidence = min(0.9, 0.5 + (price_change / (self.price_increase_threshold * 10)))
            signal_reasons.append(f"Price up {price_change:.2f}%")
        elif price_change < self.price_decrease_threshold:
            decision = TradingDecision.SELL
            price_confidence = min(0.9, 0.5 + (abs(price_change) / (abs(self.price_decrease_threshold) * 10)))
            signal_reasons.append(f"Price down {price_change:.2f}%")
        else:
            # No clear signal from price change
            price_confidence = 0.5
        
        # 2. Volume Analysis
        volume_signal = volume_analysis.get('signal', TradingDecision.HOLD)
        volume_confidence = volume_analysis.get('confidence', 0.5)
        if volume_signal != TradingDecision.HOLD:
            if volume_signal == decision:
                # Volume confirms the price signal
                signal_reasons.append(f"Volume spike factor: {volume_analysis.get('factor', 0):.2f}x")
            elif decision == TradingDecision.HOLD:
                # Only have volume signal, use it
                decision = volume_signal
                signal_reasons.append(f"Volume-based signal: {volume_signal.value}")
        
        # 3. Moving Average Analysis
        ma_signal = moving_averages.get('signal', TradingDecision.HOLD)
        ma_confidence = moving_averages.get('confidence', 0.5)
        if ma_signal != TradingDecision.HOLD:
            if ma_signal == decision:
                # MA confirms existing signal
                signal_reasons.append(f"MA ({self.ma_short_period}/{self.ma_long_period}) confirms")
            elif decision == TradingDecision.HOLD:
                # Only have MA signal, use it
                decision = ma_signal
                signal_reasons.append(f"MA ({self.ma_short_period}/{self.ma_long_period}) crossover")
        
        # 4. RSI Analysis
        if self.use_rsi_signals and rsi_data:
            rsi_signal = rsi_data.get('signal', TradingDecision.HOLD)
            rsi_confidence = rsi_data.get('confidence', 0.5)
            rsi_value = rsi_data.get('value', 50)
            
            if rsi_signal != TradingDecision.HOLD:
                if rsi_signal == decision:
                    # RSI confirms existing signal
                    signal_reasons.append(f"RSI ({rsi_value:.1f}) confirms")
                elif decision == TradingDecision.HOLD:
                    # Only have RSI signal, use it
                    decision = rsi_signal
                    signal_reasons.append(f"RSI-based signal: {rsi_value:.1f}")
                    confidence = rsi_confidence
                elif rsi_signal != decision:
                    # RSI contradicts other signals
                    logger.debug(f"RSI signal {rsi_signal.value} contradicts other signals {decision.value} for {symbol}")
                    # Don't completely override but reduce confidence
                    confidence *= 0.7
                    signal_reasons.append(f"RSI ({rsi_value:.1f}) contradicts")
        
        # 5. Final Decision Logic - Combine all indicators
        # If we still have HOLD, return None
        if decision == TradingDecision.HOLD:
            logger.debug(f"HOLD for {symbol}: No clear signals")
            return None
        
        # Calculate final confidence as weighted average of individual confidences
        # Weight more heavily the price and RSI signals
        if self.use_rsi_signals and rsi_data and rsi_data.get('signal') != TradingDecision.HOLD:
            confidence = (price_confidence * 0.3) + (volume_confidence * 0.2) + (ma_confidence * 0.2) + (rsi_data.get('confidence', 0.5) * 0.3)
        else:
            confidence = (price_confidence * 0.4) + (volume_confidence * 0.3) + (ma_confidence * 0.3)
        
        confidence = min(0.95, confidence)  # Cap confidence at 0.95
        
        # Calculate position size based on risk management
        position_size = self._calculate_position_size(symbol, price_bars, volatility)
        
        logger.info(
            f"{decision.value.upper()} signal for {symbol}: "
            f"Confidence: {confidence:.2f}, "
            f"Reasons: {', '.join(signal_reasons)}"
        )
        
        # Create the trade signal with comprehensive metadata
        return {
            "symbol": symbol,
            "action": decision.value.lower(),
            "price": current_price,
            "confidence": confidence,
            "signal_type": "polygon_comprehensive",
            "metadata": {
                "price_change_pct": price_change,
                "current_price": current_price,
                "previous_price": previous_bar.get('c'),
                "volume": latest_bar.get('v', 0),
                "volume_change": volume_analysis.get('factor', 1.0),
                "ma_short": moving_averages.get('ma_short', 0),
                "ma_long": moving_averages.get('ma_long', 0),
                "rsi": rsi_data.get('value') if rsi_data else None,
                "volatility": volatility,
                "reasons": signal_reasons,
                "suggested_position_size": position_size,
                "data_source": "polygon.io"
            }
        }
    
    def _calculate_price_change(self, latest: Dict[str, Any], previous: Dict[str, Any]) -> float:
        """Calculate percentage price change between two periods"""
        return (latest['c'] - previous['c']) / previous['c'] * 100
    
    def _analyze_volume(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze volume patterns for trading signals
        
        Returns:
            Dictionary with volume analysis results
        """
        if len(price_data) < 5:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5, "factor": 1.0}
            
        # Calculate average volume from previous periods (excluding most recent)
        latest_volume = price_data[0].get('v', 0)
        if latest_volume == 0:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5, "factor": 1.0}
            
        previous_volumes = [d.get('v', 0) for d in price_data[1:5] if d.get('v', 0) > 0]
        if not previous_volumes:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5, "factor": 1.0}
            
        avg_volume = sum(previous_volumes) / len(previous_volumes)
        if avg_volume == 0:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5, "factor": 1.0}
            
        # Calculate volume spike factor
        volume_factor = latest_volume / avg_volume
        
        result = {
            "factor": volume_factor,
            "latest_volume": latest_volume,
            "avg_volume": avg_volume,
            "signal": TradingDecision.HOLD,
            "confidence": 0.5
        }
        
        # Significant volume spike with price increase
        if volume_factor >= self.volume_spike_threshold:
            # Check price direction to determine signal
            price_change = self._calculate_price_change(price_data[0], price_data[1])
            if price_change > 0:
                result["signal"] = TradingDecision.BUY
                result["confidence"] = min(0.9, 0.5 + (volume_factor / (self.volume_spike_threshold * 2)))
            elif price_change < 0:
                result["signal"] = TradingDecision.SELL
                result["confidence"] = min(0.9, 0.5 + (volume_factor / (self.volume_spike_threshold * 2)))
                
        return result
    
    def _calculate_moving_averages(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate moving averages and generate signals based on crossovers
        
        Returns:
            Dictionary with moving average analysis results
        """
        # Need enough data for the long-term MA
        if len(price_data) < self.ma_long_period:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5}
            
        # Extract closing prices in chronological order (oldest to newest)
        # Note: Polygon data is typically in reverse chronological order
        closes = [bar['c'] for bar in reversed(price_data[:self.ma_long_period])]
        
        if len(closes) < self.ma_long_period:
            return {"signal": TradingDecision.HOLD, "confidence": 0.5}
        
        # Calculate simple moving averages
        ma_short = sum(closes[-self.ma_short_period:]) / self.ma_short_period
        ma_long = sum(closes) / self.ma_long_period
        
        # Calculate previous day's MAs to detect crossovers
        prev_closes = [bar['c'] for bar in reversed(price_data[1:self.ma_long_period+1])]
        if len(prev_closes) >= self.ma_long_period:
            prev_ma_short = sum(prev_closes[-self.ma_short_period:]) / self.ma_short_period
            prev_ma_long = sum(prev_closes) / self.ma_long_period
        else:
            # Not enough data for previous day MA
            prev_ma_short = ma_short
            prev_ma_long = ma_long
        
        result = {
            "ma_short": ma_short,
            "ma_long": ma_long,
            "signal": TradingDecision.HOLD,
            "confidence": 0.5,
        }
        
        # Golden Cross - Short MA crosses above Long MA
        if ma_short > ma_long and prev_ma_short <= prev_ma_long:
            result["signal"] = TradingDecision.BUY
            # Confidence based on the strength of the crossover
            crossover_strength = (ma_short - ma_long) / ma_long * 100
            result["confidence"] = min(0.9, 0.5 + (crossover_strength / 5))
            result["crossover"] = "golden"
        
        # Death Cross - Short MA crosses below Long MA
        elif ma_short < ma_long and prev_ma_short >= prev_ma_long:
            result["signal"] = TradingDecision.SELL
            # Confidence based on the strength of the crossover
            crossover_strength = (ma_long - ma_short) / ma_long * 100
            result["confidence"] = min(0.9, 0.5 + (crossover_strength / 5))
            result["crossover"] = "death"
        
        # Already in a trend - adjust confidence based on trend strength
        elif ma_short > ma_long:
            # In uptrend
            result["trend"] = "up"
            trend_strength = (ma_short - ma_long) / ma_long * 100
            if trend_strength > 5:  # Strong uptrend
                result["signal"] = TradingDecision.BUY
                result["confidence"] = min(0.7, 0.5 + (trend_strength / 20))
        
        elif ma_short < ma_long:
            # In downtrend
            result["trend"] = "down"
            trend_strength = (ma_long - ma_short) / ma_long * 100
            if trend_strength > 5:  # Strong downtrend
                result["signal"] = TradingDecision.SELL
                result["confidence"] = min(0.7, 0.5 + (trend_strength / 20))
        
        return result
    
    def _analyze_rsi(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate and analyze RSI for trading signals
        
        Args:
            price_data: List of price bars
            
        Returns:
            Dictionary with RSI analysis results
        """
        # Make sure we have enough data points
        if len(price_data) < self.rsi_period + 1:
            logger.debug(f"Not enough data for RSI calculation (need {self.rsi_period + 1}, got {len(price_data)})")
            return None
            
        # We can either calculate RSI directly or use the Polygon client's method
        try:
            # Use Polygon client's RSI calculation
            rsi_data = self.polygon_client._calculate_rsi(price_data, self.rsi_period)
            if not rsi_data or 'value' not in rsi_data:
                # Fall back to direct calculation
                rsi_data = self._calculate_rsi_directly(price_data)
        except Exception as e:
            logger.warning(f"Error calculating RSI via client, falling back to direct calculation: {str(e)}")
            rsi_data = self._calculate_rsi_directly(price_data)
            
        if not rsi_data or 'value' not in rsi_data:
            logger.warning("Failed to calculate RSI")
            return None
            
        rsi_value = rsi_data['value']
        
        # Initialize result
        result = {
            "value": rsi_value,
            "period": self.rsi_period,
            "signal": TradingDecision.HOLD,
            "confidence": 0.5
        }
        
        # Generate signals based on RSI thresholds
        if rsi_value <= self.rsi_oversold:
            # Oversold condition - potential buy signal
            result["signal"] = TradingDecision.BUY
            # More confidence the lower the RSI goes below oversold threshold
            oversold_strength = (self.rsi_oversold - rsi_value) / self.rsi_oversold
            result["confidence"] = min(0.9, 0.5 + oversold_strength)
            result["condition"] = "oversold"
        elif rsi_value >= self.rsi_overbought:
            # Overbought condition - potential sell signal
            result["signal"] = TradingDecision.SELL
            # More confidence the higher the RSI goes above overbought threshold
            overbought_strength = (rsi_value - self.rsi_overbought) / (100 - self.rsi_overbought)
            result["confidence"] = min(0.9, 0.5 + overbought_strength)
            result["condition"] = "overbought"
            
        return result
    
    def _calculate_rsi_directly(self, price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate RSI directly from price data (fallback if client method fails)
        
        Args:
            price_data: List of price bars
            
        Returns:
            Dictionary with RSI value and data
        """
        if len(price_data) < self.rsi_period + 1:
            return {"value": 50, "signal": TradingDecision.HOLD, "confidence": 0.5}
            
        # Get closes in chronological order
        closes = [bar['c'] for bar in reversed(price_data)]
        
        gains = []
        losses = []
        
        # Calculate price changes
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        # Calculate initial averages
        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period
        
        # Calculate final RSI
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
        return {
            "value": rsi,
            "period": self.rsi_period
        }
    
    def _calculate_volatility(self, price_data: List[Dict[str, Any]]) -> float:
        """
        Calculate historical volatility from price data
        
        Returns:
            Annualized volatility as a percentage
        """
        if len(price_data) < 5:
            return 0.0
            
        # Extract closing prices
        closes = [bar['c'] for bar in price_data]
        
        # Calculate daily returns
        returns = []
        for i in range(len(closes) - 1):
            daily_return = (closes[i] / closes[i+1]) - 1
            returns.append(daily_return)
        
        if not returns:
            return 0.0
            
        # Calculate standard deviation of returns
        try:
            std_dev = statistics.stdev(returns)
            # Annualize volatility (assuming daily data, multiply by sqrt(252))
            annualized_vol = std_dev * math.sqrt(252)
            return annualized_vol * 100  # Convert to percentage
        except statistics.StatisticsError:
            return 0.0
    
    def _calculate_position_size(self, symbol: str, price_data: List[Dict[str, Any]], volatility: float = None) -> float:
        """
        Calculate optimal position size based on risk management principles
        
        Args:
            symbol: Trading symbol
            price_data: Historical price data
            volatility: Pre-calculated volatility or None to calculate
            
        Returns:
            Suggested position size in dollars
        """
        from src.config import config
        
        # Get the base amount to work with
        if hasattr(config.trading, 'use_fixed_amount') and config.trading.use_fixed_amount:
            base_amount = config.trading.trade_fixed_amount
        else:
            # Use a percentage of portfolio if fixed amount not set
            # This would require getting current portfolio value
            # For now, just use default amount
            base_amount = 100.0
        
        # If volatility adjustment is disabled, return base amount
        if not self.volatility_adjustment:
            return base_amount
        
        # Calculate volatility if not provided
        if volatility is None:
            volatility = self._calculate_volatility(price_data)
        
        if volatility <= 0:
            return base_amount
        
        # Typical market volatility baseline (S&P 500 average is around 15%)
        baseline_volatility = 15.0
        
        # Adjustment factor - inversely proportional to volatility
        # Higher volatility = lower position size
        adjustment = baseline_volatility / max(volatility, 5.0)
        
        # Apply risk management - adjust position size based on volatility
        # but don't go below 20% or above 150% of base amount
        adjusted_amount = base_amount * min(max(adjustment, 0.2), 1.5)
        
        logger.debug(
            f"Position sizing for {symbol}: "
            f"Base={base_amount:.2f}, "
            f"Volatility={volatility:.2f}%, "
            f"Adjusted={adjusted_amount:.2f}"
        )
        
        return adjusted_amount
    
    def get_required_data(self) -> List[str]:
        """Get required data keys for this strategy"""
        return ["polygon_data"] 