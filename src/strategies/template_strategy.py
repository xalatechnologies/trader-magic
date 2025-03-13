"""
Template for creating new trading strategies.
Copy this file and rename both the file and the class to create a new strategy.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from src.utils import TradeSignal, TradingDecision, get_logger
from src.strategies.base_strategy import BaseStrategy

logger = get_logger("template_strategy")

class TemplateStrategy(BaseStrategy):
    """
    Template trading strategy that can be used as a starting point for creating
    new strategies.
    """
    
    # Override these class variables to provide strategy metadata
    name = "Template Strategy"
    description = "Template for creating new strategies"
    
    def __init__(self):
        """Initialize your strategy"""
        super().__init__()
        # Define your strategy parameters here
        self.parameter1 = 70.0
        self.parameter2 = 30.0
    
    def configure(self, parameter1: float = 70.0, parameter2: float = 30.0):
        """
        Configure the strategy parameters
        
        Args:
            parameter1: Description of parameter1
            parameter2: Description of parameter2
        """
        self.parameter1 = parameter1
        self.parameter2 = parameter2
        logger.info(f"Strategy configured with parameter1: {parameter1}, parameter2: {parameter2}")
    
    def process_data(self, symbol: str, data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Process data and generate trading signals
        
        Args:
            symbol: The trading symbol (e.g., BTC/USD)
            data: Data containing trading indicators
            
        Returns:
            TradeSignal or None if no action should be taken
        """
        # Check if we have the required data
        required_data = self.get_required_data()
        for key in required_data:
            if key not in data or not data[key]:
                logger.warning(f"Missing {key} data for {symbol}")
                return None
        
        # Implement your trading logic here
        # This is where you would analyze the data and decide whether to
        # generate a BUY, SELL, or HOLD signal
        
        # For this template, we'll just return None (no signal)
        logger.debug(f"No trading signal generated for {symbol}")
        return None
        
        # Example of generating a signal:
        """
        return TradeSignal(
            symbol=symbol,
            decision=TradingDecision.BUY,  # or SELL or HOLD
            confidence=0.75,  # 0.0 to 1.0
            rsi_value=data.get('rsi', {}).get('value', 50.0),
            timestamp=datetime.now()
        )
        """
    
    def get_required_data(self) -> List[str]:
        """Get required data keys for this strategy"""
        # Return a list of the data keys required by your strategy
        return ["sample_data"]  # Replace with your required data keys 