# 🔌 API Integrations

TraderMagic connects with several external APIs to provide its functionality. This document explains how to configure and optimize these integrations.

## 📊 TAAPI.io for Technical Indicators

TraderMagic uses TAAPI.io to retrieve RSI (Relative Strength Index) data, which serves as the primary technical indicator for trading decisions.

### 🔑 API Key Configuration

Add your TAAPI.io API key to the `.env` file:

```
TAAPI_API_KEY=your_taapi_key_here
```

### ⏱️ Rate Limits

TAAPI.io has different rate limits based on your subscription tier:

| Tier   | Rate Limit             | Recommended Poll Interval |
|--------|------------------------|---------------------------|
| Free   | 1 request / 15 seconds | 300 seconds (5 minutes)   |
| Basic  | 5 requests / 15 seconds| 60 seconds (1 minute)     |
| Pro    | 30 requests / 15 seconds | 10 seconds             |
| Expert | 75 requests / 15 seconds | 5 seconds              |

Configure the polling interval in your `.env` file:

```
POLL_INTERVAL=300  # Adjust based on your subscription tier
```

For multiple symbols, the system automatically calculates spacing between requests to stay within rate limits.

### 🪙 Supported Symbols

When using the free tier of TAAPI.io, you are limited to the following symbols from Binance:

```
BTC/USDT, ETH/USDT, XRP/USDT, LTC/USDT, XMR/USDT
```

Update your `.env` file to use only supported symbols:

```
SYMBOLS=BTC/USDT,ETH/USDT
```

## 💹 Alpaca for Trade Execution

TraderMagic uses Alpaca for executing trades, offering both paper trading and live trading capabilities.

### 🔑 API Key Configuration

Add your Alpaca API credentials to the `.env` file:

```
ALPACA_API_KEY=your_alpaca_key_here
ALPACA_API_SECRET=your_alpaca_secret_here
```

### 📝 Paper Trading Mode

For testing without real money, enable paper trading:

```
ALPACA_PAPER_TRADING=true
```

This uses Alpaca's paper trading API which simulates real trading without using actual funds.

### 🔰 Pattern Day Trading Rules

For stock trading in the US, Pattern Day Trading (PDT) rules apply to accounts under $25,000. The system can enforce these rules:

```
ALPACA_ENFORCE_PDT_RULES=true  # Prevent more than 3 day trades in 5 business days
```

Note: PDT rules don't apply to crypto trading or paper trading accounts, so the system automatically bypasses the rules in these cases.

## 🧠 Ollama for AI Decision-Making

TraderMagic uses Ollama to run an LLM (Large Language Model) locally for making trading decisions.

### 🤖 Model Configuration

Configure the model to use:

```
OLLAMA_MODEL=llama3.2:latest  # Default LLM model
OLLAMA_HOST=http://ollama:11434  # When using Docker
```

### 🔄 Using Local Ollama

If you already have Ollama installed on your host machine:

1. Download the required model manually:
   ```bash
   ollama pull llama3.2:latest  # or your chosen model
   ```

2. Update the host in your `.env` file:
   ```
   OLLAMA_HOST=http://localhost:11434
   ```

3. Update `docker-compose.yml` to remove the Ollama service dependency.

### 🧩 Model Alternatives

Ollama supports multiple models. Some alternatives you might consider:

```
OLLAMA_MODEL=llama3:latest  # Smaller footprint
OLLAMA_MODEL=mistral:latest  # Alternative architecture
```

Larger models generally provide better analysis but require more resources.