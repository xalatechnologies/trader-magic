#!/usr/bin/env python
"""
Enhanced Polygon.io Integration Example

This script demonstrates the advanced features of the Polygon.io integration
in the TraderMagic platform, including:

1. Advanced real-time signal generation with volume analysis
2. News sentiment analysis for trading signals
3. Backtesting capabilities
4. Technical indicators (RSI, Moving Averages)
5. Risk management features

For a focused RSI signal visualization and testing, 
run the dedicated script: python -m examples.test_rsi_signals

Usage:
    python -m examples.enhanced_polygon_example
"""

import os
import sys
import time
import json
import logging
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.utils import get_logger
from src.data_retrieval.polygon_client import PolygonClient
from src.strategies.polygon_strategy import PolygonStrategy
from src.strategies.news_sentiment_strategy import NewsSentimentStrategy
from src.backtest.backtest_engine import BacktestEngine
from src.utils.sentiment_analyzer import analyze_sentiment

logger = get_logger("polygon_example")
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_polygon_client():
    """Test basic Polygon client functionality"""
    print("\n" + "="*80)
    print("TESTING POLYGON CLIENT FUNCTIONALITY")
    print("="*80)
    
    client = PolygonClient()
    
    # Test ticker details
    symbols = ["AAPL", "MSFT", "GOOGL"]
    for symbol in symbols:
        print(f"\nGetting details for {symbol}:")
        details = client.get_ticker_details(symbol)
        if details:
            print(f"  Name: {details.get('name')}")
            print(f"  Type: {details.get('type')}")
            print(f"  Market: {details.get('market')}")
            print(f"  Primary Exchange: {details.get('primary_exchange')}")
            print(f"  Currency: {details.get('currency_name')}")
        else:
            print(f"  Failed to get details for {symbol}")
    
    # Test aggregates (bars)
    symbol = "AAPL"
    print(f"\nGetting recent aggregate bars for {symbol}:")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    bars = client.get_aggregates(
        symbol,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "1d"
    )
    
    if bars:
        print(f"  Retrieved {len(bars)} bars")
        for i, bar in enumerate(bars[:3]):
            print(f"  Bar {i+1}: Date: {datetime.fromtimestamp(bar.get('timestamp')/1000).strftime('%Y-%m-%d')}, "
                 f"Open: ${bar.get('open'):.2f}, Close: ${bar.get('close'):.2f}, "
                 f"Volume: {bar.get('volume')}")
        
        # Plot the close prices if we have data
        if len(bars) > 0:
            plt.figure(figsize=(10, 6))
            dates = [datetime.fromtimestamp(bar.get('timestamp')/1000) for bar in bars]
            closes = [bar.get('close') for bar in bars]
            plt.plot(dates, closes)
            plt.title(f"{symbol} Close Price")
            plt.xlabel("Date")
            plt.ylabel("Price ($)")
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(f"{symbol}_close_prices.png")
            print(f"  Saved {symbol}_close_prices.png")
    else:
        print(f"  Failed to get bars for {symbol}")
    
    # Test previous close
    print(f"\nGetting previous close for {symbol}:")
    prev_close = client.get_previous_close(symbol)
    if prev_close:
        print(f"  Previous Close: ${prev_close.get('close'):.2f} on "
             f"{datetime.fromtimestamp(prev_close.get('timestamp')/1000).strftime('%Y-%m-%d')}")
    else:
        print(f"  Failed to get previous close for {symbol}")

def test_news_sentiment():
    """Test news sentiment analysis"""
    print("\n" + "="*80)
    print("TESTING NEWS SENTIMENT ANALYSIS")
    print("="*80)
    
    client = PolygonClient()
    
    # Test ticker news with sentiment
    symbols = ["AAPL", "TSLA", "AMZN"]
    for symbol in symbols:
        print(f"\nGetting news with sentiment for {symbol}:")
        news_items = client.get_latest_news_with_sentiment(symbol, max_items=3)
        
        if news_items:
            print(f"  Retrieved {len(news_items)} news items")
            for i, news in enumerate(news_items):
                print(f"  News {i+1}: {news.get('title')}")
                print(f"    Published: {news.get('published_utc')}")
                print(f"    Sentiment: {news.get('sentiment', {}).get('sentiment', 'N/A')}")
                print(f"    Score: {news.get('sentiment', {}).get('score', 'N/A')}")
                print(f"    Explanation: {news.get('sentiment', {}).get('explanation', 'N/A')}")
                print()
            
            # Generate trading signal from news
            print(f"  Generating news-based trading signal for {symbol}:")
            signal = client.generate_news_signal(news_items)
            if signal:
                print(f"    Signal: {signal.get('action', 'NONE').upper()}")
                print(f"    Confidence: {signal.get('confidence', 0):.2f}")
                print(f"    Based on average sentiment: {signal.get('avg_sentiment', 0):.2f}")
            else:
                print("    No trading signal generated from news")
        else:
            print(f"  No news items found for {symbol}")

def test_polygon_strategy():
    """Test the enhanced polygon strategy"""
    print("\n" + "="*80)
    print("TESTING ENHANCED POLYGON STRATEGY")
    print("="*80)
    
    # Create and configure strategy
    strategy = PolygonStrategy()
    strategy.configure({
        "volume_spike_threshold": 1.5,
        "price_change_trigger": 0.01,
        "ma_short_period": 20,
        "ma_long_period": 50,
        "use_rsi_signals": True,  # Enable RSI signals
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "enabled": True
    })
    
    client = PolygonClient()
    
    # Test with a few symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]
    for symbol in symbols:
        print(f"\nTesting strategy for {symbol}:")
        
        # Fetch data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        bars = client.get_aggregates(
            symbol,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            "1d"
        )
        
        if not bars:
            print(f"  No data available for {symbol}")
            continue
            
        # Prepare data for strategy
        latest_price = bars[-1].get('close')
        data = {
            "symbol": symbol,
            "price": latest_price,
            "timestamp": bars[-1].get('timestamp'),
            "polygon_data": {
                "bars": bars,
                "open": bars[-1].get('open'),
                "high": bars[-1].get('high'),
                "low": bars[-1].get('low'),
                "close": bars[-1].get('close'),
                "volume": bars[-1].get('volume'),
                "previous_day_close": bars[-2].get('close') if len(bars) > 1 else None
            }
        }
        
        # Process data with strategy
        signal = strategy.process_data(data)
        
        if signal:
            print(f"  Generated signal: {signal.get('action').upper()}")
            print(f"  Confidence: {signal.get('confidence', 0):.2f}")
            print(f"  Signal type: {signal.get('signal_type', 'unknown')}")
            
            # Print RSI if available
            rsi_value = signal.get('metadata', {}).get('rsi')
            if rsi_value is not None:
                print(f"  Current RSI: {rsi_value:.2f}")
                
            print(f"  Signal reasons:")
            for reason in signal.get('metadata', {}).get('reasons', []):
                print(f"    - {reason}")
        else:
            print(f"  No trading signal generated for {symbol}")
            
        # Calculate and display current RSI
        if len(bars) > 14:
            try:
                rsi_data = client._calculate_rsi(bars, 14)
                if rsi_data and 'value' in rsi_data:
                    print(f"  Current RSI: {rsi_data['value']:.2f}")
                    if rsi_data['value'] >= 70:
                        print(f"  RSI ALERT: Overbought condition ({rsi_data['value']:.2f})")
                    elif rsi_data['value'] <= 30:
                        print(f"  RSI ALERT: Oversold condition ({rsi_data['value']:.2f})")
            except Exception as e:
                print(f"  Error calculating RSI: {str(e)}")
                
        print(f"\n  For detailed RSI analysis and visualization, run: python -m examples.test_rsi_signals")

def test_backtest():
    """Test backtesting capabilities"""
    print("\n" + "="*80)
    print("TESTING BACKTESTING ENGINE")
    print("="*80)
    
    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.001,
        risk_per_trade=0.02
    )
    
    # Create strategies for testing
    polygon_strategy = PolygonStrategy()
    polygon_strategy.configure({
        "volume_spike_threshold": 1.5,
        "price_change_trigger": 0.015,
        "ma_short_period": 20,
        "ma_long_period": 50,
        "use_rsi_signals": True,  # Enable RSI signals
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "enabled": True
    })
    
    news_strategy = NewsSentimentStrategy()
    news_strategy.configure({
        "sentiment_threshold": 0.6,
        "bearish_threshold": 0.4,
        "min_news_count": 2,
        "enabled": True
    })
    
    # Define test parameters
    symbol = "AAPL"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # 3 months
    
    print(f"\nRunning backtest for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Run polygon strategy backtest
    print("\nTesting Polygon Strategy:")
    polygon_results = engine.run_backtest(
        strategy=polygon_strategy,
        symbols=[symbol],
        start_date=start_date,
        end_date=end_date,
        timeframe="1d",
        verbose=True
    )
    
    # Reset the engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.001,
        risk_per_trade=0.02
    )
    
    # Run news sentiment strategy backtest
    print("\nTesting News Sentiment Strategy:")
    news_results = engine.run_backtest(
        strategy=news_strategy,
        symbols=[symbol],
        start_date=start_date,
        end_date=end_date,
        timeframe="1d",
        verbose=True
    )
    
    # Save results
    os.makedirs("backtest_results", exist_ok=True)
    
    # Save polygon results
    with open("backtest_results/polygon_results.json", "w") as f:
        json.dump(polygon_results, f, indent=4, default=str)
    
    # Save news results
    with open("backtest_results/news_results.json", "w") as f:
        json.dump(news_results, f, indent=4, default=str)
    
    print("\nBacktest results saved to backtest_results/ directory")
    
    # Plot equity curves
    if polygon_results.get('equity_curve') and news_results.get('equity_curve'):
        print("\nGenerating equity curve comparison...")
        
        # Generate plots in the future implementation
        print("Plots would be generated here in a full implementation")

def main():
    """Main function to run the example"""
    print("\n" + "="*80)
    print("ENHANCED POLYGON.IO INTEGRATION EXAMPLE")
    print("="*80)
    
    # Ensure Polygon API key is set
    if not config.polygon.api_key:
        print("ERROR: Polygon API key not set. Please set POLYGON_API_KEY in your .env file.")
        return
    
    print("\nPolygon API Key:", "*" * len(config.polygon.api_key))
    print("Base URL:", config.polygon.base_url)
    
    # Additional information about RSI testing
    print("\nNOTE: For detailed RSI signal testing and visualization:")
    print("      run: python -m examples.test_rsi_signals")
    
    # Run tests
    try:
        test_polygon_client()
        test_news_sentiment()
        test_polygon_strategy()
        test_backtest()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        
    except Exception as e:
        import traceback
        print(f"\nERROR: {str(e)}")
        traceback.print_exc()
        
if __name__ == "__main__":
    main() 