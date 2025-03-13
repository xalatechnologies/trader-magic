# Trading Strategies Module

This module provides a framework for implementing and managing trading strategies in TraderMagic.

## Overview

The strategies module allows you to create, register, and manage different trading strategies. Each strategy can analyze market data and generate trading signals based on its own logic.

## Components

- **BaseStrategy**: Abstract base class that all strategies must inherit from
- **StrategyRegistry**: Registry for managing and retrieving strategy implementations
- **StrategyManager**: Singleton manager that handles running strategies and processing signals

## Available Strategies

1. **RSI Strategy**: Makes trading decisions based on Relative Strength Index (RSI) values
   - Buy when RSI is below the oversold threshold (default: 30)
   - Sell when RSI is above the overbought threshold (default: 70)
   - Hold otherwise

2. **News Strategy**: Makes trading decisions based on news sentiment analysis
   - Buy when sentiment score is above the positive threshold (default: 70)
   - Sell when sentiment score is below the negative threshold (default: 30)
   - Hold otherwise

## Creating a New Strategy

To create a new trading strategy:

1. Create a new file in the `src/strategies` directory (e.g., `my_strategy.py`)
2. Inherit from the `BaseStrategy` class
3. Implement the required methods:
   - `process_data`: Process market data and return a trading signal
   - `get_required_data`: Return a list of required data keys

Example:

```python
from src.strategies.base_strategy import BaseStrategy
from src.utils import TradeSignal, TradeDecision

class MyStrategy(BaseStrategy):
    name = "My Custom Strategy"
    description = "A custom trading strategy based on XYZ indicator"
    
    def __init__(self):
        self.threshold = 50.0
        
    def configure(self, threshold=50.0):
        self.threshold = threshold
        
    def process_data(self, symbol, data):
        # Get the required data
        my_indicator = data.get('my_indicator')
        
        if not my_indicator:
            return None
            
        # Generate a trading signal based on the indicator
        if my_indicator > self.threshold:
            return TradeSignal(
                symbol=symbol,
                decision=TradeDecision.BUY,
                confidence=0.8
            )
        elif my_indicator < self.threshold / 2:
            return TradeSignal(
                symbol=symbol,
                decision=TradeDecision.SELL,
                confidence=0.8
            )
        else:
            return TradeSignal(
                symbol=symbol,
                decision=TradeDecision.HOLD,
                confidence=0.5
            )
    
    def get_required_data(self):
        return ['my_indicator']
```

4. Register your strategy in `src/strategies/__init__.py`:

```python
from src.strategies.base_strategy import BaseStrategy, StrategyRegistry
from src.strategies.rsi_strategy import RSIStrategy
from src.strategies.news_strategy import NewsStrategy
from src.strategies.my_strategy import MyStrategy  # Import your strategy

# Register strategies
StrategyRegistry.register(RSIStrategy)
StrategyRegistry.register(NewsStrategy)
StrategyRegistry.register(MyStrategy)  # Register your strategy

__all__ = ['BaseStrategy', 'StrategyRegistry', 'RSIStrategy', 'NewsStrategy', 'MyStrategy']
```

## Using the Strategy Manager

The `StrategyManager` provides methods to:

- Enable/disable strategies
- Process data through all enabled strategies
- Start/stop automatic polling for data

You can control the strategy manager through the web UI or via the API endpoints:

- `GET /api/strategies`: List all available strategies
- `POST /api/strategies/<strategy_name>`: Enable/disable a strategy
- `POST /api/start_strategy_manager`: Start the strategy manager polling
- `POST /api/stop_strategy_manager`: Stop the strategy manager polling
- `GET /api/signals`: Get all current trading signals

## Configuration

Set the following environment variables in your `.env` file:

```
# Strategy Manager Configuration
AUTO_START_STRATEGIES=true  # Set to 'true' to automatically start the strategy manager on startup
``` 