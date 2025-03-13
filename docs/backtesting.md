# Backtesting Guide

This guide provides detailed information on how to use the TraderMagic backtesting system to evaluate trading strategies using historical data.

## Introduction

Backtesting is the process of testing a trading strategy against historical data to determine its effectiveness before risking real capital. The TraderMagic backtesting engine allows you to:

- Test multiple trading strategies against historical market data
- Compare performance across different symbols and time periods
- Analyze risk and return metrics to optimize your strategies
- Generate visualizations of performance

## Getting Started

### Prerequisites

Before running backtests, ensure you have:

1. Configured your Polygon.io API key in your `.env` file
2. Installed the required dependencies (pandas, matplotlib, numpy)
3. Selected the appropriate strategy and symbols to test

### Basic Usage

The backtesting functionality is available through the command-line interface:

```bash
python -m src.scripts.run_backtest --strategy <strategy_name> --symbols <symbol_list> [OPTIONS]
```

#### Required Arguments

- `--strategy`: The strategy to test (polygon, crypto, rsi, news_sentiment, or all)
- `--symbols`: Comma-separated list of symbols to test (e.g., AAPL,MSFT,GOOGL)

#### Optional Arguments

- `--start_date`: Start date for backtest (YYYY-MM-DD, default: 1 year ago)
- `--end_date`: End date for backtest (YYYY-MM-DD, default: today)
- `--timeframe`: Data timeframe (1d, 1h, 15m, 5m, 1m, default: 1d)
- `--initial_capital`: Initial capital for backtest (default: 10000.0)
- `--risk_per_trade`: Risk per trade as a decimal (default: 0.02 = 2%)
- `--commission`: Commission rate as a decimal (default: 0.001 = 0.1%)
- `--output_dir`: Directory to save results (default: ./backtest_results)
- `--verbose`: Enable verbose output
- `--plot`: Generate plots of results

### Examples

#### Testing a Single Strategy

```bash
# Test the Polygon strategy on AAPL for all of 2022
python -m src.scripts.run_backtest --strategy polygon --symbols AAPL --start_date 2022-01-01 --end_date 2022-12-31 --plot
```

#### Comparing Multiple Strategies

```bash
# Compare all strategies on AAPL
python -m src.scripts.run_backtest --strategy all --symbols AAPL --plot
```

#### Testing Multiple Symbols

```bash
# Test the RSI strategy on multiple tech stocks
python -m src.scripts.run_backtest --strategy rsi --symbols AAPL,MSFT,GOOGL,AMZN --plot
```

#### Testing Different Timeframes

```bash
# Test on hourly data instead of daily
python -m src.scripts.run_backtest --strategy polygon --symbols AAPL --timeframe 1h --start_date 2022-01-01 --end_date 2022-01-31 --plot
```

## Understanding Backtest Results

### Performance Metrics

The backtesting engine calculates the following metrics:

- **Total Return**: Overall percentage return of the strategy
- **Annualized Return**: Return normalized to an annual basis
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (higher is better)
- **Win Rate**: Percentage of winning trades
- **Profit Factor**: Gross profit divided by gross loss
- **Average Win/Loss**: Average profit per winning/losing trade
- **Average Holding Period**: Average duration of trades

### Visualizations

When using the `--plot` flag, the following visualizations are generated:

- **Equity Curve**: Shows the growth of portfolio value over time
- **Drawdown Chart**: Visualizes drawdowns throughout the testing period
- **Monthly Returns Heatmap**: Shows returns by month (when sufficient data is available)

All plots are saved to the specified output directory.

## Advanced Backtesting

### Strategy-Specific Parameters

Each strategy accepts custom parameters:

#### Polygon Strategy
- `--volume_threshold`: Volume spike threshold (default: 2.0)
- `--price_change_trigger`: Price change percentage to trigger signals (default: 0.02 = 2%)

#### RSI Strategy
- `--rsi_upper`: RSI upper threshold for signals (default: 70)
- `--rsi_lower`: RSI lower threshold for signals (default: 30)

### Risk Management

The backtesting engine implements several risk management techniques:

1. **Position Sizing**: Positions are sized based on defined risk per trade and volatility
2. **Maximum Exposure**: No single position can exceed 25% of portfolio
3. **Slippage Modeling**: Simulates market impact with configurable slippage
4. **Commission Costs**: Accounts for trading fees in performance calculations

## Implementing Custom Strategies

You can implement custom strategies for backtesting by:

1. Creating a new strategy class that inherits from `BaseStrategy`
2. Implementing the `process_data` method that generates trading signals
3. Adding your strategy to the `create_strategy` function in `run_backtest.py`

Example of a minimal custom strategy:

```python
from src.strategies.base_strategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("my_custom")
        
    def configure(self, config):
        super().configure(config)
        self.my_parameter = config.get("my_parameter", 0.5)
        
    def process_data(self, data):
        symbol = data.get("symbol")
        price = data.get("price")
        
        # Generate signal based on your logic
        if some_condition:
            return {
                "symbol": symbol,
                "action": "buy",
                "price": price,
                "confidence": 0.8
            }
        
        return None
```

## Best Practices

1. **Start Simple**: Begin with a single strategy and a limited time period
2. **Use Realistic Assumptions**: Configure slippage and commission to match real-world conditions
3. **Avoid Overfitting**: Test across multiple symbols and time periods
4. **Validate Results**: Use out-of-sample testing to validate strategy performance
5. **Consider Market Conditions**: Be aware of different market regimes in your test period

## Troubleshooting

### Common Issues

1. **No Data Available**
   
   If you see "No historical data found" errors, check:
   - Your Polygon.io API key is valid
   - The symbols are correct and have data for the specified period
   - The timeframe is supported by your API subscription level

2. **Slow Backtest Performance**
   
   For better performance:
   - Use daily timeframes for long periods
   - Limit the number of symbols
   - Cache historical data for repeated tests

3. **Unrealistic Results**
   
   If results seem too good to be true:
   - Double-check your slippage and commission settings
   - Verify your risk management settings
   - Check for potential look-ahead bias in your strategy

## Conclusion

Backtesting is a powerful tool for strategy development, but remember that past performance does not guarantee future results. Use backtesting as one component of your trading strategy development process, alongside forward testing and paper trading.

For more information, refer to the API documentation for the [BacktestEngine](../src/backtest/backtest_engine.py) class. 