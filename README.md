![TraderMagic](docs/img/dashboard-screenshot.png)

# Trader Magic

A microservices-based algorithmic trading platform.

## Services

Trader Magic consists of the following services:

1. **Data Retrieval**: Collects market data from various sources
2. **AI Decision**: Analyzes market data using machine learning
3. **Trade Execution**: Executes trades on supported exchanges
4. **Strategy Manager**: Manages trading strategies and generates trade signals
5. **Frontend**: Web UI for monitoring and controlling the system

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

## License

[MIT License](LICENSE)

## ✨ Features

- 🧠 **AI-powered trading decisions** using locally-run LLM models via Ollama
- 📊 **Real-time dashboards** with trade status and history
- 🛑 **Trading on/off toggle** for complete user control
- 📈 **RSI-based technical analysis** for market insights
- 🕒 **Market hours visualization** showing pre-market, regular hours, after-hours, and closed sessions
- 💰 **Flexible trade sizing** with portfolio percentage or fixed amounts
- 🔒 **Paper trading mode** for risk-free testing
- 🔄 **Redis-powered communication** between services
- 🐳 **Docker-based deployment** for easy setup

## 🏗️ System Architecture

TraderMagic consists of four main components:

1. **Data Retrieval Service** 📡 - Polls TAAPI.io for RSI data
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
- [🔍 Troubleshooting Guide](docs/troubleshooting.md) - Solving common issues

## ⚠️ Disclaimer

This trading system is provided for educational and research purposes only. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always do your own research and consider consulting a financial advisor before making investment decisions.

## 🙏 Acknowledgments

TraderMagic is inspired by the work of [Mike Russell and the Creator Magic Community](http://www.creatormagic.ai). His innovations in AI-powered creative tools have been pivotal in the development of this project.

## 📜 License

TraderMagic is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.