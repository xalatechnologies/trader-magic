"""
Trading strategy module for TraderMagic.
This module contains different trading strategies that can be used to generate trade signals.
"""

from .base_strategy import BaseStrategy, StrategyRegistry
from .rsi_strategy import RSIStrategy
from .news_strategy import NewsStrategy

# Register available strategies
StrategyRegistry.register(RSIStrategy)
StrategyRegistry.register(NewsStrategy)

__all__ = ["BaseStrategy", "StrategyRegistry", "RSIStrategy", "NewsStrategy"] 