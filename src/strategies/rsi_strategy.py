"""
RSI-based trading strategy implementation.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from src.utils import TradeSignal, TradingDecision, get_logger
from src.strategies.base_strategy import BaseStrategy

logger = get_logger("rsi_strategy")

class RSIStrategy(BaseStrategy):
    """
    RSI-based trading strategy that uses the Relative Strength Index to generate 
    trading signals based on overbought and oversold conditions.
    """
    
    name = "RSI Strategy"
    description = "Uses RSI values to identify overbought and oversold conditions"
    
    def __init__(self):
        """Initialize the RSI strategy with default thresholds"""
        super().__init__()
        # Default thresholds
        self.overbought_threshold = 70.0
        self.oversold_threshold = 30.0
    
    def configure(self, overbought_threshold: float = 70.0, oversold_threshold: float = 30.0):
        """
        Configure the strategy parameters
        
        Args:
            overbought_threshold: RSI value above which a SELL signal is generated (default: 70)
            oversold_threshold: RSI value below which a BUY signal is generated (default: 30)
        """
        self.overbought_threshold = overbought_threshold
        self.oversold_threshold = oversold_threshold
        logger.info(f"RSI Strategy configured with overbought: {overbought_threshold}, oversold: {oversold_threshold}")
    
    def process_data(self, symbol: str, data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Process RSI data and generate trading signals
        
        Args:
            symbol: The trading symbol (e.g., BTC/USD)
            data: Data containing RSI values
            
        Returns:
            TradeSignal or None if no action should be taken
        """
        # Check if we have RSI data
        if 'rsi' not in data or not data['rsi']:
            logger.warning(f"No RSI data available for {symbol}")
            return None
            
        rsi_data = data['rsi']
        rsi_value = rsi_data.get('value')
        
        if rsi_value is None:
            logger.warning(f"RSI value is missing for {symbol}")
            return None
            
        # Make trading decision based on RSI value
        decision = TradingDecision.HOLD
        confidence = 0.5  # Default confidence
        
        if rsi_value <= self.oversold_threshold:
            # Oversold condition - potential buy signal
            decision = TradingDecision.BUY
            # Calculate confidence based on how far below the threshold
            # 0 = threshold, 1 = RSI at 0
            confidence = min(0.9, 0.5 + (self.oversold_threshold - rsi_value) / (self.oversold_threshold * 2))
            logger.info(f"BUY signal for {symbol}: RSI {rsi_value} below {self.oversold_threshold}, confidence: {confidence:.2f}")
            
        elif rsi_value >= self.overbought_threshold:
            # Overbought condition - potential sell signal
            decision = TradingDecision.SELL
            # Calculate confidence based on how far above the threshold
            # 0 = threshold, 1 = RSI at 100
            confidence = min(0.9, 0.5 + (rsi_value - self.overbought_threshold) / ((100 - self.overbought_threshold) * 2))
            logger.info(f"SELL signal for {symbol}: RSI {rsi_value} above {self.overbought_threshold}, confidence: {confidence:.2f}")
            
        else:
            # No clear signal
            logger.debug(f"HOLD for {symbol}: RSI {rsi_value} in neutral range")
            return None  # No trade signal for hold
            
        # Create the trade signal
        return TradeSignal(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            rsi_value=rsi_value,
            timestamp=datetime.now()
        )
    
    def get_required_data(self) -> List[str]:
        """Get required data keys for this strategy"""
        return ["rsi"] 