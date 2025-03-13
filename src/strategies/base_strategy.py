"""
Base Strategy Interface for TraderMagic trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from src.utils import TradeSignal, get_logger

logger = get_logger("strategies")

class BaseStrategy(ABC):
    """Base interface for all trading strategies"""
    
    # Class variables for strategy metadata
    name: str = "Base Strategy"
    description: str = "Abstract base strategy"
    
    def __init__(self):
        """Initialize the strategy"""
        logger.info(f"Initializing {self.name} strategy")
    
    @abstractmethod
    def process_data(self, symbol: str, data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Process data and generate a trade signal if appropriate
        
        Args:
            symbol: Trading symbol (e.g., BTC/USD)
            data: Data for this symbol containing various indicators, prices, etc.
            
        Returns:
            TradeSignal or None if no action should be taken
        """
        pass
    
    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get strategy metadata"""
        return {
            "name": cls.name,
            "description": cls.description,
            "class": cls.__name__
        }
    
    @abstractmethod
    def get_required_data(self) -> List[str]:
        """
        Get the list of data keys required by this strategy
        
        Returns:
            List of required data keys (e.g., ["rsi", "price"])
        """
        pass


class StrategyRegistry:
    """Registry for available trading strategies"""
    
    _strategies = {}
    
    @classmethod
    def register(cls, strategy_class):
        """Register a strategy class"""
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"Strategy {strategy_class.__name__} must inherit from BaseStrategy")
            
        cls._strategies[strategy_class.__name__] = strategy_class
        logger.info(f"Registered strategy: {strategy_class.__name__}")
        return strategy_class
    
    @classmethod
    def get_strategy(cls, name: str) -> Optional[BaseStrategy]:
        """Get a strategy instance by name"""
        if name not in cls._strategies:
            logger.error(f"Strategy '{name}' not found in registry")
            return None
            
        return cls._strategies[name]()
    
    @classmethod
    def list_strategies(cls) -> List[Dict[str, Any]]:
        """List all available strategies with their metadata"""
        return [strategy_class.get_info() for strategy_class in cls._strategies.values()] 