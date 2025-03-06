# 🚀 Installation Guide

Follow these steps to get TraderMagic up and running on your system.

## 📋 Prerequisites

Before getting started, make sure you have:

- **Docker** with Docker Compose support
- **~4GB Disk Space** (for Docker images and Ollama models)

### 🔑 Required External Accounts

TraderMagic requires accounts with these external services:

#### 📊 TAAPI.io
- **Purpose**: Provides technical indicators (RSI values) for trading decisions
- **Pricing**: Offers free tier with limited usage, and paid tiers for more features
- **Signup**: [Create TAAPI.io Account](https://taapi.io/signup)
- **Documentation**: [TAAPI API Docs](https://taapi.io/documentation/)
- **API Key**: After signup, generate an API key from your dashboard

#### 💹 Alpaca Markets
- **Purpose**: Executes trades based on system signals
- **Features**: Offers paper trading for safe testing without real money
- **Signup**: [Create Alpaca Account](https://app.alpaca.markets/signup)
- **Documentation**: [Alpaca API Docs](https://alpaca.markets/docs/)
- **API Keys**: After signup, generate API key and secret from your dashboard settings

> **Note**: The free tier of TAAPI.io has limitations on which symbols you can use and how frequently you can poll data. Consider upgrading if you need more symbols or faster updates.

## 🔧 Step 1: Clone the Repository

```bash
git clone https://github.com/rawveg/trader-magic.git
cd trader-magic
```

## ⚙️ Step 2: Configure Environment Variables

Copy the example environment file:

```bash
cp .env.sample .env
```

Then edit the `.env` file with your favorite text editor and fill in your API keys:

```bash
# Essential API Keys
TAAPI_API_KEY=your_taapi_api_key_here
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here

# Trading Configuration (defaults shown)
SYMBOLS=BTC/USD,ETH/USD   # Can also add stocks like AAPL,TSLA,MSFT
TRADE_PERCENTAGE=2.0
TRADE_FIXED_AMOUNT=10.0
TRADE_USE_FIXED=false

# Safety Settings (recommended for starting)
ALPACA_PAPER_TRADING=true
ALPACA_DEBUG_MODE=true
```

## 🏗️ Step 3: Start the Services

Launch the application using Docker Compose:

```bash
docker compose up -d
```

This command starts all the required services in detached mode:
- Redis database
- Ollama AI model server
- Data retrieval service
- AI decision engine
- Trade execution service
- Web dashboard

## 🖥️ Step 4: Access the Dashboard

Once all services are running, access the web dashboard:

```
http://localhost:9753
```

The first startup might take a few minutes as the system:
1. Downloads necessary Docker images
2. Downloads Ollama models
3. Initializes connections to external APIs

## 🔄 Restarting After Configuration Changes

After making changes to the `.env` file, use the provided restart script:

```bash
chmod +x restart.sh     # Make it executable (first time only)
./restart.sh            # Restart all services with new config
```

## 🔍 Verifying Installation

Check that all services are running:

```bash
docker compose ps
```

You should see the following services in the "Up" state:
- redis
- ollama
- frontend
- data_retrieval
- ai_decision
- trade_execution

## 🔧 Troubleshooting

If you encounter issues:

1. Check the logs for each service:
   ```bash
   docker compose logs frontend
   docker compose logs data_retrieval
   docker compose logs ai_decision
   docker compose logs trade_execution
   ```

2. Verify API keys are correctly set in your `.env` file

3. Make sure all required ports are available on your system:
   - 9753 (Frontend)
   - 6379 (Redis)
   - 11434 (Ollama)

## 📈 Supported Symbol Formats

TraderMagic supports both cryptocurrency and stock symbols:

### Cryptocurrency Symbols
Use the standard format with a slash:
```
BTC/USDT, ETH/USDT, XRP/USDT, etc.
```

### Stock Symbols
Use the simple ticker format:
```
AAPL, TSLA, MSFT, NVDA, etc.
```

> **Note**: The system automatically converts stock tickers to the proper format for API requests. For example, `TSLA` is converted to `TSLA/USD` when querying TAAPI.io.

### Free Tier Limitations
If you're using the free tier of TAAPI.io, you're limited to specific cryptocurrency pairs only:
- BTC/USDT
- ETH/USDT
- XRP/USDT
- LTC/USDT
- XMR/USDT

For full symbol support, consider upgrading to a paid tier.