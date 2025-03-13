![TraderMagic](docs/img/dashboard-screenshot.png)

# Trader Magic

A microservices-based algorithmic trading platform.

## Services

Trader Magic consists of the following services:

1. **Data Retrieval**: Collects market data from various sources (TAAPI, Polygon.io, news)
2. **AI Decision**: Analyzes market data using machine learning
3. **Trade Execution**: Executes trades on supported exchanges
4. **Strategy Manager**: Manages trading strategies and generates trade signals
5. **Frontend**: Web UI for monitoring and controlling the system

## Data Sources

TraderMagic collects market data from various sources, including:

* **TAAPI.io**: For accessing technical indicators
* **Polygon.io**: For real-time and historical market data, company details, and news
* **News sources**: For sentiment analysis and event-driven trading

## Advanced Features

### Polygon.io Integration

Our advanced Polygon.io integration provides:

- **Real-time Stock Data**: Access to live market data for equities
- **Volume Analysis**: Detection of unusual volume spikes that may indicate market moves
- **Technical Indicators**: Calculation of moving averages, RSI, and other indicators
- **Historical Data**: Comprehensive historical data for backtesting strategies
- **News Sentiment**: Analysis of financial news sentiment to identify market trends

### Backtesting Engine

The platform includes a powerful backtesting system:

- **Historical Performance Testing**: Test strategies against historical market data
- **Multiple Timeframes**: Backtest on daily, hourly, or minute-level data
- **Risk Management**: Dynamic position sizing based on volatility and risk parameters
- **Performance Metrics**: Comprehensive metrics including Sharpe ratio, drawdown, win rate
- **Visualization**: Generate charts of equity curves, drawdowns, and monthly returns

### AI-Powered News Sentiment Analysis

Leverage financial news for trading decisions:

- **Sentiment Scoring**: Analyze news articles for bullish or bearish sentiment
- **OpenAI Integration**: Use advanced language models for nuanced sentiment analysis
- **Fallback Methods**: Keyword-based analysis when API connectivity is unavailable
- **Signal Generation**: Convert news sentiment into actionable trading signals
- **Confidence Scaling**: Adjust position sizes based on sentiment strength

## Technical Indicators

TraderMagic supports various technical indicators for generating trading signals:

### RSI (Relative Strength Index)

The platform includes dedicated tools for RSI analysis and visualization:

* **RSI Signal Generation**: Configure overbought/oversold thresholds and generate trading signals
* **RSI Visualization Tool**: Analyze historical RSI patterns with price correlation
* **Command-line Testing**: Run `python -m src.scripts.run_rsi_test --symbol AAPL,MSFT,TSLA` to test RSI-based signals

#### RSI Testing Options

```
python -m src.scripts.run_rsi_test --symbol AAPL --days 120 --period 14 --overbought 70 --oversold 30
```

Parameters:
- `--symbol`: Stock symbol(s) to analyze (comma-separated for multiple)
- `--days`: Number of days of historical data to analyze (default: 120)
- `--period`: RSI calculation period (default: 14)
- `--overbought`: RSI overbought threshold (default: 70)
- `--oversold`: RSI oversold threshold (default: 30)
- `--save-plots`: Save plots to files instead of displaying

### Other Indicators

* **Moving Averages**: Short and long-term trend identification
* **Volume Analysis**: Detect unusual trading activity
* **News Sentiment**: Generate signals based on news sentiment

## Architecture

The system uses a microservices architecture with Redis for inter-service communication. Each service runs in its own Docker container and communicates asynchronously.

## Getting Started

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/trader-magic.git
   cd trader-magic
   ```

2. Create a `.env` file with your configuration (see `.env.example`)

3. Build and start the services:
   ```
   docker-compose build
   docker-compose up -d
   ```

4. Visit the dashboard at `http://localhost:9753`

## Development

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Node.js 14+ (for frontend development)

### Local Development

You can run individual services locally for development:

```
python -m src.data_retrieval.service  # Run data retrieval service
python -m src.ai_decision.service      # Run AI decision service
python -m src.trade_execution.service  # Run trade execution service
python -m src.strategies.service       # Run strategy manager service
python frontend/app.py                # Run frontend
```

### Running Backtests

Test your strategies against historical data:

```bash
# Run a backtest on AAPL and MSFT using the polygon strategy
python -m src.scripts.run_backtest --strategy polygon --symbols AAPL,MSFT --start_date 2022-01-01 --end_date 2022-12-31 --plot

# Compare multiple strategies
python -m src.scripts.run_backtest --strategy all --symbols AAPL --start_date 2022-01-01 --end_date 2022-12-31 --plot

# Test news sentiment strategy with custom parameters
python -m src.scripts.run_backtest --strategy news_sentiment --symbols AAPL,GOOGL,AMZN --start_date 2022-01-01 --end_date 2022-12-31 --plot
```

## Troubleshooting

### Common Issues

1. **Strategy Manager Not Detected**
   
   If you see "Backend strategy manager not detected", make sure the strategy manager service is running. Check with:
   
   ```
   docker ps | grep strategy_manager
   ```
   
   If it's not running, start it with:
   
   ```
   docker-compose up -d strategy_manager
   ```

2. **Data Retrieval Issues**
   
   If data retrieval is failing, check the logs:
   
   ```
   docker logs data_retrieval
   ```

3. **Polygon.io API Issues**

   If you're experiencing issues with Polygon.io data:
   
   ```
   # Test the Polygon.io integration
   python -m test_polygon_api
   
   # Check the API key in your .env file
   POLYGON_API_KEY=your_api_key_here
   ```

## License

[MIT License](LICENSE)

## ✨ Features

- 🧠 **AI-powered trading decisions** using locally-run LLM models via Ollama
- 📊 **Real-time dashboards** with trade status and history
- 🛑 **Trading on/off toggle** for complete user control
- 📈 **RSI-based technical analysis** for market insights
- 📰 **News sentiment analysis** for event-driven trading strategies
- 🔍 **Volume spike detection** for identifying unusual market activity
- 📉 **Backtesting engine** for historical strategy validation
- 🕒 **Market hours visualization** showing pre-market, regular hours, after-hours, and closed sessions
- 💰 **Flexible trade sizing** with portfolio percentage or fixed amounts
- 🔒 **Paper trading mode** for risk-free testing
- 🔄 **Redis-powered communication** between services
- 🐳 **Docker-based deployment** for easy setup

## 🏗️ System Architecture

TraderMagic consists of four main components:

1. **Data Retrieval Service** 📡 - Polls data sources (TAAPI.io, Polygon.io) for market data
2. **AI Decision Engine** 🧠 - Analyzes data using Ollama LLM to make trading decisions
3. **Trade Execution Service** 💹 - Interfaces with Alpaca to execute trades
4. **Web Dashboard** 🖥️ - Real-time monitoring interface

All components are containerized using Docker and communicate through Redis.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/rawveg/trader-magic.git
cd trader-magic

# Configure your environment
cp .env.sample .env
# Edit .env with your API keys

# Start the application
docker compose up -d

# Access the dashboard
# Open http://localhost:9753 in your browser
```

## 📚 Documentation

For detailed documentation on all aspects of TraderMagic, check out these guides:

- [📋 Installation Guide](docs/installation.md) - Step-by-step setup instructions
- [🏗️ Architecture Overview](docs/architecture.md) - System design and components
- [🔌 API Integrations](docs/api-integration.md) - Configuring external APIs
- [🚦 Trading Modes](docs/trading-modes.md) - Paper/live trading and debug modes
- [📊 Dashboard Features](docs/dashboard.md) - Using the web interface
- [📈 Backtesting Guide](docs/backtesting.md) - How to backtest your strategies
- [🔍 Troubleshooting Guide](docs/troubleshooting.md) - Solving common issues

## ⚠️ Disclaimer

This trading system is provided for educational and research purposes only. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always do your own research and consider consulting a financial advisor before making investment decisions.

## 🙏 Acknowledgments

TraderMagic is inspired by the work of [Mike Russell and the Creator Magic Community](http://www.creatormagic.ai). His innovations in AI-powered creative tools have been pivotal in the development of this project.

## 📜 License

TraderMagic is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.