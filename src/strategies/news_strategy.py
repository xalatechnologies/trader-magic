"""
News-based trading strategy implementation.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from src.utils import TradeSignal, TradingDecision, get_logger
from src.strategies.base_strategy import BaseStrategy

logger = get_logger("news_strategy")

class NewsStrategy(BaseStrategy):
    """
    News-based trading strategy that analyzes news sentiment to generate 
    trading signals.
    """
    
    name = "News Sentiment Strategy"
    description = "Uses news sentiment analysis to make trading decisions"
    
    def __init__(self):
        """Initialize the news strategy with default thresholds"""
        super().__init__()
        # Default thresholds
        self.positive_threshold = 70.0
        self.negative_threshold = 30.0
    
    def configure(self, positive_threshold: float = 70.0, negative_threshold: float = 30.0):
        """
        Configure the strategy parameters
        
        Args:
            positive_threshold: Sentiment score above which a BUY signal is generated (default: 70)
            negative_threshold: Sentiment score below which a SELL signal is generated (default: 30)
        """
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold
        logger.info(f"News Strategy configured with positive: {positive_threshold}, negative: {negative_threshold}")
    
    def process_data(self, symbol: str, data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Process news data and generate trading signals
        
        Args:
            symbol: The trading symbol (e.g., BTC/USD)
            data: Data containing news and sentiment analysis
            
        Returns:
            TradeSignal or None if no action should be taken
        """
        # Check if we have news data with sentiment
        if 'news_sentiment' not in data or not data['news_sentiment']:
            logger.debug(f"No news sentiment data available for {symbol}")
            return None
            
        sentiment_data = data['news_sentiment']
        sentiment_score = sentiment_data.get('score')
        headline = sentiment_data.get('headline', 'Unnamed news')
        
        if sentiment_score is None:
            logger.warning(f"Sentiment score is missing for {symbol}")
            return None
            
        # Make trading decision based on sentiment score
        decision = TradingDecision.HOLD
        confidence = 0.5  # Default confidence
        
        if sentiment_score >= self.positive_threshold:
            # Positive sentiment - potential buy signal
            decision = TradingDecision.BUY
            # Calculate confidence based on how far above the threshold
            confidence = min(0.9, 0.5 + (sentiment_score - self.positive_threshold) / ((100 - self.positive_threshold) * 2))
            logger.info(f"BUY signal for {symbol}: News sentiment {sentiment_score} above {self.positive_threshold}, confidence: {confidence:.2f}")
            logger.info(f"Headline: {headline}")
            
        elif sentiment_score <= self.negative_threshold:
            # Negative sentiment - potential sell signal
            decision = TradingDecision.SELL
            # Calculate confidence based on how far below the threshold
            confidence = min(0.9, 0.5 + (self.negative_threshold - sentiment_score) / (self.negative_threshold * 2))
            logger.info(f"SELL signal for {symbol}: News sentiment {sentiment_score} below {self.negative_threshold}, confidence: {confidence:.2f}")
            logger.info(f"Headline: {headline}")
            
        else:
            # No clear signal
            logger.debug(f"HOLD for {symbol}: News sentiment {sentiment_score} in neutral range")
            return None  # No trade signal for hold
            
        # Create the trade signal
        return TradeSignal(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            rsi_value=50.0,  # Default RSI value, not used for this strategy
            timestamp=datetime.now()
        )
    
    def get_required_data(self) -> List[str]:
        """Get required data keys for this strategy"""
        return ["news_sentiment"] 