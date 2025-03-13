"""
Trading strategy module for TraderMagic.
This module contains different trading strategies that can be used to generate trade signals.
"""

from .base_strategy import BaseStrategy, StrategyRegistry
from .rsi_strategy import RSIStrategy
from .news_strategy import NewsStrategy
from .polygon_strategy import PolygonStrategy

# Register available strategies
StrategyRegistry.register(RSIStrategy)
StrategyRegistry.register(NewsStrategy)
StrategyRegistry.register(PolygonStrategy)

__all__ = ["BaseStrategy", "StrategyRegistry", "RSIStrategy", "NewsStrategy", "PolygonStrategy"] 