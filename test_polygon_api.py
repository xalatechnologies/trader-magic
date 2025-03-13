#!/usr/bin/env python3
"""
Test script to verify Polygon.io API integration.
This script tests the Polygon.io API client we've integrated into trader-magic.
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure we have a Polygon API key
polygon_api_key = os.getenv("POLYGON_API_KEY")
if not polygon_api_key or polygon_api_key == "YOUR_POLYGON_API_KEY_HERE":
    print("Error: POLYGON_API_KEY is not set in your .env file")
    print("Please add your Polygon.io API key to the .env file and try again")
    sys.exit(1)

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our Polygon client
from src.data_retrieval.polygon_client import PolygonClient

def test_api():
    """Test the Polygon.io API integration"""
    
    # Create a Polygon client
    polygon = PolygonClient()
    
    # Test symbols
    test_symbols = ["AAPL", "MSFT", "GOOGL"]
    
    print(f"\n{'=' * 50}")
    print(f"Testing Polygon.io API with API key: {polygon_api_key[:5]}...{polygon_api_key[-5:]}")
    print(f"{'=' * 50}\n")
    
    # Test get_ticker_details
    for symbol in test_symbols:
        print(f"\nTesting get_ticker_details for {symbol}:")
        try:
            details = polygon.get_ticker_details(symbol)
            if details:
                print(f"  ✓ Successfully retrieved ticker details")
                print(f"    Name: {details.get('name')}")
                print(f"    Market: {details.get('market')}")
                print(f"    Primary Exchange: {details.get('primary_exchange')}")
            else:
                print(f"  ✗ Failed to get ticker details")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
    
    # Test get_aggregate_bars
    print(f"\nTesting get_aggregate_bars:")
    for symbol in test_symbols:
        try:
            bars = polygon.get_aggregate_bars(symbol, limit=5)
            if bars:
                print(f"  ✓ Successfully retrieved {len(bars)} bars for {symbol}")
                print(f"    Latest close price: ${bars[0]['c']:.2f}")
                print(f"    Previous close price: ${bars[1]['c']:.2f}")
            else:
                print(f"  ✗ Failed to get aggregate bars for {symbol}")
        except Exception as e:
            print(f"  ✗ Error for {symbol}: {str(e)}")
    
    # Test get_previous_close
    print(f"\nTesting get_previous_close:")
    for symbol in test_symbols:
        try:
            prev_close = polygon.get_previous_close(symbol)
            if prev_close:
                print(f"  ✓ Successfully retrieved previous close for {symbol}")
                print(f"    Close: ${prev_close['c']:.2f}")
                print(f"    Volume: {prev_close.get('v', 0)}")
            else:
                print(f"  ✗ Failed to get previous close for {symbol}")
        except Exception as e:
            print(f"  ✗ Error for {symbol}: {str(e)}")
    
    # Test signal generation
    print(f"\nTesting signal generation:")
    for symbol in test_symbols:
        try:
            bars = polygon.get_aggregate_bars(symbol, limit=5)
            if bars:
                signal = polygon.generate_signal_from_data(symbol, bars)
                if signal:
                    print(f"  ✓ Generated {signal.decision.value.upper()} signal for {symbol}")
                    print(f"    Confidence: {signal.confidence:.2f}")
                    print(f"    Price change: {signal.metadata.get('price_change_pct', 0):.2f}%")
                else:
                    print(f"  ℹ No trading signal generated for {symbol} (HOLD)")
            else:
                print(f"  ✗ Failed to get data for signal generation for {symbol}")
        except Exception as e:
            print(f"  ✗ Error for {symbol}: {str(e)}")
    
    print(f"\n{'=' * 50}")
    print(f"Polygon.io API test complete!")
    print(f"{'=' * 50}\n")

if __name__ == "__main__":
    test_api() 