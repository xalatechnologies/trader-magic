# 🚦 Trading Modes

TraderMagic has several configuration options that control how trades are executed and displayed.

## 🔄 Paper vs. Live Trading

TraderMagic can operate in two primary trading environments:

### 📝 Paper Trading Mode

Paper trading uses Alpaca's sandbox environment instead of their live trading API. It makes real API calls but uses simulated money.

```
ALPACA_PAPER_TRADING=true   # Use Alpaca's paper trading API (recommended)
ALPACA_PAPER_TRADING=false  # Use Alpaca's live trading API (real money!)
```

### 📊 Debug Mode 

Debug mode is completely local and doesn't make any API calls at all - even to Alpaca's paper trading environment:

```
ALPACA_DEBUG_MODE=true   # Simulate trades locally with no API calls
ALPACA_DEBUG_MODE=false  # Make actual API calls (to paper or live API based on setting above)
```

When debug mode is enabled:
1. **NO API calls** are made to Alpaca (even if paper trading is enabled)
2. A prominent purple banner appears at the top of the dashboard saying "DEBUG MODE"
3. A "Debug Mode (No API Calls)" badge is shown in the system info section
4. All trades will show an order ID starting with "sim-"

**⚠️ IMPORTANT**: These two settings are independent. You can have any combination:

| Paper Trading | Debug Mode | Behavior |
|---------------|------------|----------|
| true          | true       | No API calls, completely simulated trades |
| true          | false      | Makes API calls to Alpaca's paper trading environment |
| false         | true       | No API calls, completely simulated trades |
| false         | false      | Makes API calls to Alpaca's live trading environment (real money!) |

For development and testing, we recommend:
```
ALPACA_PAPER_TRADING=true   # Use sandbox environment
ALPACA_DEBUG_MODE=true      # No API calls made
```

When you're ready to test with actual API calls:
```
ALPACA_PAPER_TRADING=true   # Use sandbox environment
ALPACA_DEBUG_MODE=false     # Make real API calls to paper trading
```

## ⚙️ Trading Control

TraderMagic includes a safety feature that prevents automatic trading until explicitly enabled by the user.

By default, trading is disabled when the system starts for safety. This means:
- The system will collect RSI data and generate trading signals
- The AI will make decisions on what actions to take
- But no actual trades will be executed until trading is enabled through the UI

To enable trading:
1. Click the green "Start Trading" button on the dashboard
2. The button will turn red and change to "Stop Trading" when active
3. Click again at any time to immediately disable trading

This safety feature gives you complete control over when the system can execute trades, allowing you to monitor signal quality before committing to automatic trading. Trading is always disabled when the application is restarted.

## 💰 Trade Amount Settings

TraderMagic supports two modes for determining trade sizes:

### 📊 Portfolio Percentage (Default)

By default, the system trades a percentage of your portfolio value (default: 2%). This means:
- The amount traded scales with your account size
- As your portfolio grows, so do your trade sizes
- Trade amounts automatically adjust based on asset price changes

To configure percentage-based trading:
```
TRADE_PERCENTAGE=2.0   # Percentage of portfolio to trade 
TRADE_USE_FIXED=false  # Use percentage mode
```

### 💵 Fixed Amount Trading

Alternatively, you can configure the system to use a consistent dollar amount for each trade:
- Each trade will use exactly the specified amount (e.g., always trade $10)
- The system calculates the appropriate quantity based on the current price
- This is useful for consistency in testing and for limiting exposure

To configure fixed amount trading:
```
TRADE_FIXED_AMOUNT=10.0  # Fixed amount in USD for each trade
TRADE_USE_FIXED=true     # Use fixed amount mode
```

You can change between these modes directly in the dashboard without modifying the .env file.

## 🕒 Market Hours Visualization

TraderMagic visualizes different market trading sessions for stocks. The system automatically detects and displays the current market status based on the Eastern Time (ET) zone:

### 📉 Market Status Types

The system tracks four distinct market states:

| Status | Description | Visual Indicator | Time (ET) |
|--------|-------------|------------------|-----------|
| **Open** | Regular market hours | Circle markers | 9:30 AM - 4:00 PM |
| **Pre-Market** | Early trading session | Triangle markers | 4:00 AM - 9:30 AM |
| **After-Hours** | Extended trading after close | Square markers | 4:00 PM - 8:00 PM |
| **Closed** | Market closed (overnight/weekends) | X markers | 8:00 PM - 4:00 AM / Weekends |

### 📊 Chart Visualization

Price charts automatically display different point styles based on when the candle data was recorded:

- **Regular Hours**: Standard circular points (smaller size)
- **Pre-Market**: Triangle markers (larger size to highlight early trading)
- **After-Hours**: Rotated square markers
- **Closed Market**: X-shaped markers for data points when markets are closed

This visual differentiation helps you:
- Identify which trading session influenced a price movement
- Recognize patterns specific to pre-market or after-hours trading
- Understand price data in context of market hours
- Factor market session into your trading decisions

Cryptocurrency pairs (like BTC/USDT) are always shown with "Open" market status since they trade 24/7.