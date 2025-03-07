# 📊 Dashboard Features

The TraderMagic dashboard provides a real-time view of your trading activities with an intuitive, responsive interface.

![Dashboard Screenshot](./img/dashboard-screenshot.jpg)

## 📈 Key Features

- **Current RSI values** for each symbol
- **Latest AI trading decisions** (Buy, Sell, Hold)
- **Trade execution status** with detailed results
- **Recent activity history** log
- **Trading toggle** button to control when trades are executed
- **Market status visualization** showing regular, pre-market, after-hours, and closed market sessions
- **Price charts** with session-specific markers
- **Automatic updates** every 15 seconds
- **Manual refresh** button for on-demand updates

## 🔄 Real-Time Data

Both automatic and manual refreshes retrieve data from Redis cache, not directly from external APIs, ensuring no additional load on rate-limited services.

## 💰 Account Summary

The account summary section provides key financial metrics:

- **Portfolio Value**: Total value of your account
- **Cash Balance**: Available cash in your account
- **Buying Power**: Available funds for trading
- **Daily Change**: Today's portfolio change (color-coded):
  - Green: Positive change (+)
  - Red: Negative change (-)
  - Shows both dollar amount and percentage

## 🌙 Theme Options

The dashboard supports light and dark modes:

- **Auto**: Follows your system preference
- **Light**: Classic light theme for daytime use
- **Dark**: Reduced eye strain for nighttime use

The theme selector ensures all options remain clearly visible regardless of the current theme.

## 🔧 Trade Settings Control

Easily modify trading parameters directly from the dashboard:

1. **Trade Mode Selection**:
   - Portfolio Percentage: Trade a percentage of your account
   - Fixed Amount: Trade a specific dollar amount

2. **Amount Configuration**:
   - Adjust percentage (0.1% to 100%)
   - Set fixed dollar amount ($1 minimum)

3. **Trading Control**:
   - Start/Stop button to enable or disable trading
   - Prevents accidental trades until you're ready

## 📱 Responsive Design

The dashboard is designed to work on all devices:
- Desktop: Full-featured trading dashboard
- Tablet: Optimized layout for medium screens
- Mobile: Compact view for monitoring on the go

## 📊 Price Charts with Market Context

Price charts provide valuable context about market conditions:

### 🕒 Market Session Indicators

Different marker styles show when a price candle was recorded:
- **Regular Market Hours**: Small circular points
- **Pre-Market**: Triangle markers
- **After-Hours**: Rotated square markers
- **Closed Market**: X markers

### 📈 Session-Aware Visualization

This visual distinction helps you:
- Identify price movements during different market sessions
- Recognize patterns unique to pre-market or after-hours trading
- Distinguish between high-volume regular hours and thinner extended hours
- Factor market conditions into trading decisions

### 🔄 Automatic Timezone Adjustment

The system automatically determines the appropriate market session based on Eastern Time (ET), the standard for US stock markets. This provides context about potential liquidity and volatility during different trading sessions.

## 🧪 Debug Interface

For testing purposes, a special debug page is available at `http://localhost:9753/debug`:

- Direct trade execution buttons
- Current configuration display
- Test trade functionality

This debug interface is invaluable for verifying that your trade settings are working correctly without waiting for trade signals.