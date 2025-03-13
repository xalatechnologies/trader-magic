#!/usr/bin/env python
"""
RSI Signal Testing Script

This script tests and visualizes RSI-based trading signals using the
enhanced Polygon strategy implementation. It shows how RSI values
are calculated and how they generate trading signals.

Usage:
    python -m examples.test_rsi_signals
"""

import os
import sys
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.utils import get_logger, TradingDecision
from src.data_retrieval.polygon_client import PolygonClient
from src.strategies.polygon_strategy import PolygonStrategy

logger = get_logger("test_rsi_signals")
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def fetch_historical_data(symbol, days=120):
    """Fetch historical data for a symbol"""
    client = PolygonClient()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Fetch daily bars
    bars = client.get_aggregates(
        symbol,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "1d"
    )
    
    if not bars:
        logger.error(f"No data found for {symbol}")
        return None
        
    logger.info(f"Retrieved {len(bars)} bars for {symbol}")
    return bars

def calculate_rsi_series(bars, period=14):
    """Calculate a full RSI series for all bars"""
    # Sort bars chronologically (oldest first)
    sorted_bars = sorted(bars, key=lambda x: x['t'])
    
    closes = [bar['c'] for bar in sorted_bars]
    dates = [datetime.fromtimestamp(bar['t']/1000) for bar in sorted_bars]
    
    # Calculate price changes
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(0, change) for change in changes]
    losses = [max(0, -change) for change in changes]
    
    # Calculate RSI
    rsi_values = []
    
    # Need at least period+1 data points to start
    if len(closes) <= period:
        return dates, [], closes
    
    # First RSI value uses simple average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Handle division by zero
    if avg_loss == 0:
        first_rs = float('inf')
    else:
        first_rs = avg_gain / avg_loss
        
    first_rsi = 100 - (100 / (1 + first_rs))
    rsi_values.append(first_rsi)
    
    # Rest of RSI uses smoothed average
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
        
        if avg_loss == 0:
            rs = float('inf')
        else:
            rs = avg_gain / avg_loss
            
        rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)
    
    # Align dates with RSI values (RSI starts at period)
    rsi_dates = dates[period:]
    price_values = closes[period:]
    
    return rsi_dates, rsi_values, price_values

def generate_signals(strategy, symbol, bars):
    """Generate signals for each data point using the strategy"""
    signals = []
    
    # We'll process each day as if it were the current day
    for i in range(len(bars)):
        if i < 30:  # Skip the first few days as we need enough data for indicators
            continue
            
        # Get historical data up to this point
        historical_bars = bars[:(i+1)]
        
        # Create data dictionary for strategy
        data = {
            "symbol": symbol,
            "price": historical_bars[-1]['c'],
            "polygon_data": {
                "bars": historical_bars
            }
        }
        
        # Process with strategy
        signal = strategy.process_data(data)
        
        # Store signal with date
        signals.append({
            "date": datetime.fromtimestamp(historical_bars[-1]['t']/1000),
            "price": historical_bars[-1]['c'],
            "signal": signal
        })
    
    return signals

def visualize_rsi_signals(symbol, bars, rsi_dates, rsi_values, price_values, signals):
    """Create visualization of RSI signals"""
    # Prepare figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2, 1]})
    fig.suptitle(f'RSI Signal Analysis for {symbol}', fontsize=16)
    
    # Plot price in top subplot
    ax1.plot(rsi_dates, price_values, label='Close Price', color='blue')
    ax1.set_ylabel('Price ($)')
    ax1.set_title(f'{symbol} Price')
    ax1.grid(True)
    
    # Plot RSI in bottom subplot
    ax2.plot(rsi_dates, rsi_values, label='RSI', color='purple')
    ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought (70)')
    ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold (30)')
    ax2.axhline(y=50, color='k', linestyle='--', alpha=0.3)
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.grid(True)
    
    # Plot buy/sell signals
    buy_dates = []
    buy_prices = []
    sell_dates = []
    sell_prices = []
    
    for signal_data in signals:
        signal = signal_data.get("signal")
        if not signal:
            continue
            
        # Get metadata to check if this was an RSI-based signal
        metadata = signal.get("metadata", {})
        reasons = metadata.get("reasons", [])
        
        # Only show RSI-based signals
        if not any("RSI" in reason for reason in reasons):
            continue
            
        if signal.get("action") == "buy":
            buy_dates.append(signal_data["date"])
            buy_prices.append(signal_data["price"])
        elif signal.get("action") == "sell":
            sell_dates.append(signal_data["date"])
            sell_prices.append(signal_data["price"])
    
    # Plot buy signals on price chart
    if buy_dates:
        ax1.scatter(buy_dates, buy_prices, marker='^', color='green', s=100, label='Buy Signal')
        
        # Also mark on RSI chart
        for date in buy_dates:
            # Find closest RSI date
            idx = np.abs(np.array(rsi_dates) - np.array(date)).argmin()
            if idx < len(rsi_values):
                ax2.scatter(rsi_dates[idx], rsi_values[idx], marker='^', color='green', s=100)
    
    # Plot sell signals on price chart
    if sell_dates:
        ax1.scatter(sell_dates, sell_prices, marker='v', color='red', s=100, label='Sell Signal')
        
        # Also mark on RSI chart
        for date in sell_dates:
            # Find closest RSI date
            idx = np.abs(np.array(rsi_dates) - np.array(date)).argmin()
            if idx < len(rsi_values):
                ax2.scatter(rsi_dates[idx], rsi_values[idx], marker='v', color='red', s=100)
    
    # Format x-axis to show dates nicely
    date_format = mdates.DateFormatter('%Y-%m-%d')
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(date_format)
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Add legends
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper left')
    
    # Adjust layout and display
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    
    # Save figure
    plt.savefig(f"{symbol}_rsi_signals.png")
    logger.info(f"Saved visualization to {symbol}_rsi_signals.png")
    
    # Show statistics
    print("\nRSI Signal Statistics:")
    print(f"Total Buy Signals: {len(buy_dates)}")
    print(f"Total Sell Signals: {len(sell_dates)}")
    
    # Print details of the last few signals
    print("\nRecent RSI Signals:")
    recent_signals = [s for s in signals[-10:] if s.get("signal") and 
                     any("RSI" in r for r in s.get("signal", {}).get("metadata", {}).get("reasons", []))]
    
    for i, signal_data in enumerate(recent_signals):
        signal = signal_data.get("signal")
        if signal:
            action = signal.get("action", "NONE").upper()
            confidence = signal.get("confidence", 0)
            date = signal_data["date"].strftime("%Y-%m-%d")
            price = signal_data["price"]
            reasons = signal.get("metadata", {}).get("reasons", [])
            rsi_value = signal.get("metadata", {}).get("rsi")
            
            # Only print RSI signals
            rsi_reasons = [r for r in reasons if "RSI" in r]
            if rsi_reasons:
                print(f"{i+1}. {date}: {action} @ ${price:.2f}, Conf: {confidence:.2f}, RSI: {rsi_value:.1f}")
                print(f"   Reasons: {', '.join(rsi_reasons)}")

def main():
    """Main function to test RSI signals"""
    print("\n" + "="*80)
    print("TESTING RSI SIGNALS")
    print("="*80)
    
    # Ensure Polygon API key is set
    if not config.polygon.api_key:
        print("ERROR: Polygon API key not set. Please set POLYGON_API_KEY in your .env file.")
        return
    
    # Configure the strategy with RSI-focused settings
    strategy = PolygonStrategy()
    strategy.configure({
        "enabled": True,
        "use_rsi_signals": True,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        # Higher sensitivity to price changes for more signals
        "price_increase_threshold": 1.0,
        "price_decrease_threshold": -1.0
    })
    
    # Test with multiple symbols
    symbols = ["AAPL", "MSFT", "TSLA"]
    
    for symbol in symbols:
        print(f"\nAnalyzing RSI signals for {symbol}:")
        
        # Fetch historical data
        bars = fetch_historical_data(symbol, days=180)
        if not bars:
            continue
            
        # Calculate RSI series
        rsi_dates, rsi_values, price_values = calculate_rsi_series(bars, period=14)
        
        if not rsi_values:
            print(f"  Could not calculate RSI for {symbol}")
            continue
            
        print(f"  Current RSI value: {rsi_values[-1]:.2f}")
        
        # Generate signals
        signals = generate_signals(strategy, symbol, bars)
        
        # Count RSI signals
        rsi_signals = [s for s in signals if s.get("signal") and 
                     any("RSI" in r for r in s.get("signal", {}).get("metadata", {}).get("reasons", []))]
        
        print(f"  Generated {len(signals)} total signals, {len(rsi_signals)} RSI-based signals")
        
        # Visualize
        visualize_rsi_signals(symbol, bars, rsi_dates, rsi_values, price_values, signals)
        
    print("\n" + "="*80)
    print("RSI TESTING COMPLETE")
    print("="*80)
        
if __name__ == "__main__":
    main() 