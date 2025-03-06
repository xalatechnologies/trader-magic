# 🔍 Troubleshooting Guide

This guide helps you diagnose and fix common issues with TraderMagic.

## 🛑 Common Issues

### 📊 No Trades Appearing in UI

**Symptoms**: 
- Trade signals are being generated but no trades show up in the dashboard
- You see "No recent trades" in the trade info section

**Possible Causes & Solutions**:

1. **Trading is disabled**
   - Look for the "Trading Disabled" badge in the footer
   - Click the "Start Trading" button to enable trading

2. **Debug mode is affecting behavior**
   - Check if `ALPACA_DEBUG_MODE=true` in your `.env` file
   - Set to `false` to allow real API calls

3. **Fixed amount is too low**
   - If using fixed amount mode, ensure the amount is sufficient
   - Minimum trade amount is often $1 or higher
   
4. **API credentials issue**
   - Check your Alpaca API keys in the `.env` file
   - Verify account status on Alpaca's dashboard

**Diagnostic Steps**:
1. Visit the debug dashboard at `http://localhost:9753/debug`
2. Check the current trading settings displayed
3. Try executing a manual test trade to verify functionality

### 🐢 Slow Updates or Timeouts

**Symptoms**:
- Dashboard shows stale data
- Log shows timeout errors or connection issues

**Possible Causes & Solutions**:

1. **TAAPI.io rate limits**
   - Increase the `POLL_INTERVAL` in your `.env` file
   - Consider upgrading your TAAPI.io subscription tier

2. **Network connectivity issues**
   - Check your internet connection
   - Verify that API services are reachable from your network

3. **Resource constraints**
   - Ensure your system has sufficient RAM and CPU
   - Consider scaling down to fewer symbols or simpler models

### ⚠️ API Rate Limit Errors

**Symptoms**:
- Logs show 429 errors from TAAPI.io
- No price updates for extended periods

**Solutions**:
1. Increase poll interval in `.env`:
   ```
   POLL_INTERVAL=300  # 5 minutes
   ```
   
2. Reduce number of symbols monitored:
   ```
   SYMBOLS=BTC/USD  # Just one symbol
   ```

3. Verify you're using supported symbols on your tier

### 🔌 Redis Connection Issues

**Symptoms**:
- Web UI not updating
- Errors containing "Redis connection"

**Solutions**:
1. Check the Redis logs:
   ```bash
   docker compose logs redis
   ```
   
2. Verify Redis is running:
   ```bash
   docker compose ps redis
   ```
   
3. Try restarting just the Redis container:
   ```bash
   docker compose restart redis
   ```

### 🤖 Ollama Model Issues

**Symptoms**:
- No AI decisions being made
- Errors mentioning model not found

**Solutions**:
1. Check if the model is downloaded:
   ```bash
   docker compose exec ollama ollama list
   ```
   
2. Check the Ollama logs:
   ```bash
   docker compose logs ollama
   ```
   
3. Try a different model:
   ```
   OLLAMA_MODEL=llama3:latest  # Change in .env file
   ```
   
4. Restart the Ollama service:
   ```bash
   docker compose restart ollama
   ```

## 📋 Log Analysis

When troubleshooting, check the logs for specific services:

```bash
# Check all logs together
docker compose logs -f

# Check specific service logs
docker compose logs -f data_retrieval
docker compose logs -f ai_decision
docker compose logs -f trade_execution
docker compose logs -f frontend
```

## 🔄 Reset Procedure

If you need a complete reset:

1. Stop all services:
   ```bash
   docker compose down
   ```

2. Remove Redis volumes:
   ```bash
   docker volume rm tradermagic_redis_data
   ```

3. Start fresh:
   ```bash
   docker compose up -d
   ```

## 🆘 Getting Help

If you've tried the troubleshooting steps above and still need help:

1. Check the GitHub issues: https://github.com/rawveg/trader-magic/issues
2. Submit a new issue with:
   - Detailed description of your problem
   - Relevant logs (with sensitive information removed)
   - Your configuration settings (without API keys)
   - Steps you've already taken to troubleshoot