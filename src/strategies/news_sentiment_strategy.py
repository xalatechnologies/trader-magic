"""
News Sentiment Strategy - Trading strategy based on news sentiment analysis
"""

from typing import Dict, Any, Optional, List

from src.strategies.base_strategy import BaseStrategy
from src.data_retrieval.polygon_client import PolygonClient
from src.utils import get_logger
from src.utils.sentiment_analyzer import analyze_sentiment

logger = get_logger("news_sentiment_strategy")

class NewsSentimentStrategy(BaseStrategy):
    """
    Trading strategy that generates signals based on news sentiment.
    Uses sentiment analysis of news headlines and content to determine market direction.
    """
    
    def __init__(self):
        """Initialize the News Sentiment Strategy"""
        super().__init__("news_sentiment")
        self.polygon_client = PolygonClient()
        self.sentiment_threshold = 0.65  # Bullish threshold (0-1 scale)
        self.bearish_threshold = 0.35    # Bearish threshold (0-1 scale)
        self.neutral_zone = (0.4, 0.6)   # Neutral zone (no signal)
        self.min_news_count = 3          # Minimum news items to consider
        self.max_news_age_hours = 24     # Maximum age of news to consider
        self.confidence_scaling = True   # Scale confidence based on sentiment strength
        
    def configure(self, config: Dict[str, Any]):
        """
        Configure the strategy with the provided parameters
        
        Args:
            config: Dictionary of configuration parameters
        """
        super().configure(config)
        
        # Update thresholds if provided
        self.sentiment_threshold = config.get("sentiment_threshold", self.sentiment_threshold)
        self.bearish_threshold = config.get("bearish_threshold", self.bearish_threshold)
        
        # Update other settings if provided
        self.neutral_zone = config.get("neutral_zone", self.neutral_zone)
        self.min_news_count = config.get("min_news_count", self.min_news_count)
        self.max_news_age_hours = config.get("max_news_age_hours", self.max_news_age_hours)
        self.confidence_scaling = config.get("confidence_scaling", self.confidence_scaling)
        
        logger.info(f"News Sentiment Strategy configured with: "
                   f"sentiment_threshold={self.sentiment_threshold}, "
                   f"bearish_threshold={self.bearish_threshold}, "
                   f"min_news_count={self.min_news_count}")
    
    def process_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process data and generate trading signal based on news sentiment
        
        Args:
            data: Dictionary containing price and relevant data
            
        Returns:
            Dictionary with trading signal or None if no signal
        """
        if not self.enabled:
            return None
            
        symbol = data.get("symbol")
        if not symbol:
            logger.warning("No symbol provided in data")
            return None
            
        # Check if this is a stock (not crypto)
        if "/" in symbol:
            logger.debug(f"Skipping news sentiment analysis for crypto symbol: {symbol}")
            return None
            
        # Get latest news with sentiment for the symbol
        news_with_sentiment = self._get_news_with_sentiment(symbol)
        
        if not news_with_sentiment or len(news_with_sentiment) < self.min_news_count:
            logger.debug(f"Insufficient news items for {symbol}: {len(news_with_sentiment) if news_with_sentiment else 0}")
            return None
            
        # Calculate aggregate sentiment
        avg_sentiment_score, sentiment_data = self._calculate_aggregate_sentiment(news_with_sentiment)
        
        # Determine signal based on sentiment score
        signal = self._generate_signal_from_sentiment(symbol, avg_sentiment_score, data, sentiment_data)
        
        if signal:
            logger.info(f"News sentiment signal for {symbol}: {signal['action'].upper()}, "
                       f"confidence: {signal.get('confidence', 0):.2f}, "
                       f"based on {len(news_with_sentiment)} news items with avg score: {avg_sentiment_score:.2f}")
            
        return signal
    
    def _get_news_with_sentiment(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get latest news with sentiment analysis for the given symbol
        
        Args:
            symbol: The stock symbol to get news for
            
        Returns:
            List of news items with sentiment analysis
        """
        try:
            news_items = self.polygon_client.get_latest_news_with_sentiment(symbol, 
                                                                          max_items=10, 
                                                                          max_age_hours=self.max_news_age_hours)
            return news_items if news_items else []
        except Exception as e:
            logger.error(f"Error retrieving news with sentiment for {symbol}: {str(e)}")
            return []
    
    def _calculate_aggregate_sentiment(self, news_with_sentiment: List[Dict[str, Any]]) -> tuple:
        """
        Calculate aggregate sentiment from news items
        
        Args:
            news_with_sentiment: List of news items with sentiment data
            
        Returns:
            Tuple of (average sentiment score, sentiment data dictionary)
        """
        if not news_with_sentiment:
            return 0.5, {"count": 0, "bullish": 0, "bearish": 0, "neutral": 0}
            
        # Extract sentiment scores
        sentiment_scores = []
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for news in news_with_sentiment:
            sentiment = news.get("sentiment", {})
            score = sentiment.get("score", 50) / 100  # Convert 0-100 to 0-1 scale
            sentiment_scores.append(score)
            
            # Count by category
            if score > self.sentiment_threshold:
                bullish_count += 1
            elif score < self.bearish_threshold:
                bearish_count += 1
            else:
                neutral_count += 1
                
        # Calculate average score
        avg_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5
        
        # Create sentiment data summary
        sentiment_data = {
            "count": len(news_with_sentiment),
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": neutral_count,
            "scores": sentiment_scores,
            "avg_score": avg_score
        }
        
        return avg_score, sentiment_data
    
    def _generate_signal_from_sentiment(self, symbol: str, sentiment_score: float, 
                                       price_data: Dict[str, Any], 
                                       sentiment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on sentiment score
        
        Args:
            symbol: Trading symbol
            sentiment_score: Aggregate sentiment score (0-1 scale)
            price_data: Price data dictionary
            sentiment_data: Sentiment analysis data
            
        Returns:
            Signal dictionary or None if no signal
        """
        # Get current price
        current_price = price_data.get("price")
        if not current_price:
            logger.warning(f"No price data available for {symbol}")
            return None
            
        # Default confidence level
        confidence = 0.5
        
        # Check if we have a bullish signal
        if sentiment_score > self.sentiment_threshold:
            action = "buy"
            # Scale confidence based on sentiment strength
            if self.confidence_scaling:
                # Map from threshold to 1.0 -> confidence 0.5 to 1.0
                confidence = 0.5 + (0.5 * ((sentiment_score - self.sentiment_threshold) / 
                                           (1 - self.sentiment_threshold)))
                
            # Get distribution of sentiment categories for stronger signal
            bullish_ratio = sentiment_data["bullish"] / sentiment_data["count"]
            confidence = confidence * (0.5 + 0.5 * bullish_ratio)
            
            return {
                "symbol": symbol,
                "action": action,
                "price": current_price,
                "confidence": min(confidence, 0.95),  # Cap at 0.95
                "signal_type": "news_sentiment",
                "sentiment_score": sentiment_score,
                "news_count": sentiment_data["count"],
                "bullish_count": sentiment_data["bullish"],
                "neutral_count": sentiment_data["neutral"],
                "bearish_count": sentiment_data["bearish"]
            }
            
        # Check if we have a bearish signal
        elif sentiment_score < self.bearish_threshold:
            action = "sell"
            # Scale confidence based on sentiment strength
            if self.confidence_scaling:
                # Map from threshold to 0.0 -> confidence 0.5 to 1.0
                confidence = 0.5 + (0.5 * ((self.bearish_threshold - sentiment_score) / 
                                          self.bearish_threshold))
                
            # Get distribution of sentiment categories for stronger signal
            bearish_ratio = sentiment_data["bearish"] / sentiment_data["count"]
            confidence = confidence * (0.5 + 0.5 * bearish_ratio)
            
            return {
                "symbol": symbol,
                "action": action,
                "price": current_price,
                "confidence": min(confidence, 0.95),  # Cap at 0.95
                "signal_type": "news_sentiment",
                "sentiment_score": sentiment_score,
                "news_count": sentiment_data["count"],
                "bullish_count": sentiment_data["bullish"],
                "neutral_count": sentiment_data["neutral"],
                "bearish_count": sentiment_data["bearish"]
            }
            
        # No signal if in neutral zone
        return None 