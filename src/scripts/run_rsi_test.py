#!/usr/bin/env python
"""
RSI Testing Command-Line Tool

This script provides a command-line interface for testing and visualizing RSI signals
using historical stock data from Polygon.io.

Usage:
    python -m src.scripts.run_rsi_test --symbol AAPL --days 120
    python -m src.scripts.run_rsi_test --symbol AAPL,MSFT,TSLA --period 14 --overbought 75 --oversold 25
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config
from src.utils import get_logger
from src.data_retrieval.polygon_client import PolygonClient
from src.strategies.polygon_strategy import PolygonStrategy

logger = get_logger("rsi_test")
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Test RSI signals with Polygon data')
    
    parser.add_argument('--symbol', type=str, default='AAPL',
                        help='Stock symbol(s) to analyze (comma-separated for multiple)')
    parser.add_argument('--days', type=int, default=120,
                        help='Number of days of historical data to analyze')
    parser.add_argument('--period', type=int, default=14,
                        help='RSI period')
    parser.add_argument('--overbought', type=float, default=70,
                        help='RSI overbought threshold')
    parser.add_argument('--oversold', type=float, default=30,
                        help='RSI oversold threshold')
    parser.add_argument('--save-plots', action='store_true',
                        help='Save plots to files instead of displaying')
    
    return parser.parse_args()

def fetch_historical_data(symbol, days=120):
    """Fetch historical price data for the given symbol."""
    client = PolygonClient()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    bars = client.get_aggregates(
        symbol,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "1d"
    )
    
    if not bars:
        logger.error(f"No data available for {symbol}")
        return None
    
    logger.info(f"Retrieved {len(bars)} bars for {symbol}")
    return bars

def calculate_rsi_series(bars, period=14):
    """Calculate RSI values for the entire series of bars."""
    if len(bars) < period + 1:
        logger.error(f"Not enough data points to calculate RSI (need at least {period + 1})")
        return None
    
    # Extract closing prices
    closes = [bar.get('close') for bar in bars]
    
    # Calculate price changes
    price_changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    # Initialize RSI series with None values
    rsi_series = [None] * period
    
    # Calculate initial average gains and losses
    gains = [max(0, change) for change in price_changes[:period]]
    losses = [max(0, -change) for change in price_changes[:period]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Calculate RSI for the first point after the period
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    rsi_series.append(rsi)
    
    # Calculate RSI for the remaining points
    for i in range(period, len(price_changes)):
        avg_gain = ((avg_gain * (period - 1)) + max(0, price_changes[i])) / period
        avg_loss = ((avg_loss * (period - 1)) + max(0, -price_changes[i])) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_series.append(rsi)
    
    return rsi_series

def generate_signals(symbol, bars, period=14, overbought=70, oversold=30):
    """Generate trading signals based on RSI values."""
    rsi_series = calculate_rsi_series(bars, period)
    if not rsi_series:
        return None
    
    # Create strategy instance
    strategy = PolygonStrategy()
    strategy.configure({
        "use_rsi_signals": True,
        "rsi_period": period,
        "rsi_overbought": overbought,
        "rsi_oversold": oversold,
        "price_change_trigger": 0.01,  # Default value
        "volume_spike_threshold": 1.5,  # Default value
        "enabled": True
    })
    
    # Generate signals
    signals = []
    dates = []
    
    for i in range(period, len(bars)):
        # Create data dictionary for strategy
        current_data = {
            "symbol": symbol,
            "price": bars[i].get('close'),
            "timestamp": bars[i].get('timestamp'),
            "polygon_data": {
                "bars": bars[:i+1],  # Include all bars up to current
                "open": bars[i].get('open'),
                "high": bars[i].get('high'),
                "low": bars[i].get('low'),
                "close": bars[i].get('close'),
                "volume": bars[i].get('volume')
            }
        }
        
        # Process data with strategy
        signal = strategy.process_data(current_data)
        
        if signal:
            signal['bar_index'] = i
            signal['rsi'] = rsi_series[i]
            signals.append(signal)
        
        dates.append(datetime.fromtimestamp(bars[i].get('timestamp')/1000))
    
    return {
        "dates": dates,
        "rsi_series": rsi_series[period:],  # Skip initial None values
        "signals": signals,
        "closes": [bar.get('close') for bar in bars[period:]]
    }

def visualize_rsi_signals(symbol, results, overbought=70, oversold=30, save_plots=False):
    """Visualize RSI signals with price charts and RSI indicator."""
    if not results:
        logger.error(f"No results to visualize for {symbol}")
        return
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot price chart
    ax1.plot(results["dates"], results["closes"], label="Close Price")
    ax1.set_title(f"{symbol} Price with RSI Signals")
    ax1.set_ylabel("Price ($)")
    ax1.grid(True)
    
    # Plot buy signals
    buy_dates = []
    buy_prices = []
    
    # Plot sell signals
    sell_dates = []
    sell_prices = []
    
    for signal in results["signals"]:
        idx = signal["bar_index"] - len(results["closes"])  # Adjust index for sliced data
        if idx < 0:  # Skip signals outside our date range
            if signal["action"] == "BUY":
                buy_dates.append(results["dates"][idx])
                buy_prices.append(results["closes"][idx])
            elif signal["action"] == "SELL":
                sell_dates.append(results["dates"][idx])
                sell_prices.append(results["closes"][idx])
    
    if buy_dates:
        ax1.scatter(buy_dates, buy_prices, color='green', marker='^', s=100, label="Buy Signal")
    
    if sell_dates:
        ax1.scatter(sell_dates, sell_prices, color='red', marker='v', s=100, label="Sell Signal")
    
    ax1.legend()
    
    # Plot RSI
    ax2.plot(results["dates"], results["rsi_series"], label="RSI", color='purple')
    ax2.axhline(y=overbought, color='r', linestyle='--', label=f"Overbought ({overbought})")
    ax2.axhline(y=oversold, color='g', linestyle='--', label=f"Oversold ({oversold})")
    ax2.axhline(y=50, color='k', linestyle='-', alpha=0.2)
    ax2.set_title(f"{symbol} RSI Indicator")
    ax2.set_ylabel("RSI")
    ax2.set_xlabel("Date")
    ax2.set_ylim([0, 100])
    ax2.grid(True)
    ax2.legend()
    
    plt.tight_layout()
    
    # Save or show the plot
    if save_plots:
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(f"{output_dir}/{symbol}_rsi_analysis.png")
        logger.info(f"Saved plot to {output_dir}/{symbol}_rsi_analysis.png")
    else:
        plt.show()
    
    # Close the figure to free memory
    plt.close(fig)
    
    # Print signal statistics
    buy_count = sum(1 for s in results["signals"] if s["action"] == "BUY")
    sell_count = sum(1 for s in results["signals"] if s["action"] == "SELL")
    
    print(f"\nSignal Statistics for {symbol}:")
    print(f"  Total signals: {len(results['signals'])}")
    print(f"  Buy signals: {buy_count}")
    print(f"  Sell signals: {sell_count}")
    print(f"  Analysis period: {len(results['dates'])} days")
    
    # Print latest RSI value
    if results["rsi_series"]:
        latest_rsi = results["rsi_series"][-1]
        print(f"\nLatest RSI value: {latest_rsi:.2f}")
        
        if latest_rsi >= overbought:
            print(f"  ALERT: Stock is currently OVERBOUGHT ({latest_rsi:.2f})")
        elif latest_rsi <= oversold:
            print(f"  ALERT: Stock is currently OVERSOLD ({latest_rsi:.2f})")

def main():
    """Main function to run the RSI test."""
    args = parse_args()
    
    print("\n" + "="*80)
    print("RSI SIGNAL TESTING TOOL")
    print("="*80)
    
    # Ensure Polygon API key is set
    if not config.polygon.api_key:
        print("ERROR: Polygon API key not set. Please set POLYGON_API_KEY in your .env file.")
        return
    
    print(f"\nRSI Parameters:")
    print(f"  Period: {args.period}")
    print(f"  Overbought threshold: {args.overbought}")
    print(f"  Oversold threshold: {args.oversold}")
    print(f"  Historical data: {args.days} days")
    
    # Process symbols
    symbols = [s.strip() for s in args.symbol.split(',')]
    
    for symbol in symbols:
        print("\n" + "-"*80)
        print(f"ANALYZING {symbol}")
        print("-"*80)
        
        # Fetch historical data
        bars = fetch_historical_data(symbol, args.days)
        
        if not bars:
            continue
        
        # Generate signals
        results = generate_signals(
            symbol, 
            bars, 
            period=args.period, 
            overbought=args.overbought, 
            oversold=args.oversold
        )
        
        # Visualize results
        visualize_rsi_signals(
            symbol, 
            results, 
            overbought=args.overbought, 
            oversold=args.oversold,
            save_plots=args.save_plots
        )
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
if __name__ == "__main__":
    main() 