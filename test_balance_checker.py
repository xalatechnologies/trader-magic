import os
import sys
from src.utils.balance_checker import BalanceChecker

def test_balance_checker():
    """Test the BalanceChecker utility to ensure it works correctly."""
    checker = BalanceChecker()
    
    # Test getting account data
    print("Testing account data retrieval...")
    account_data = checker.get_account_data()
    print(f"Account data: Cash=${account_data.get('cash', 0):,.2f}, Buying Power=${account_data.get('buying_power', 0):,.2f}")
    
    # Test balance check
    print("\nTesting balance check for different amounts...")
    test_amounts = [100, 1000, 5000, 10000, 15000]
    for amount in test_amounts:
        has_balance, available = checker.has_sufficient_balance(amount)
        print(f"Amount needed: ${amount:,.2f}, Available: ${available:,.2f}, Sufficient: {has_balance}")
    
    # Test safe trade amount calculation
    print("\nTesting safe trade amount calculation...")
    test_symbols_prices = [
        ("BTC/USDT", 60000),
        ("ETH/USDT", 3000),
        ("XRP/USDT", 0.50),
        ("LTC/USDT", 90)
    ]
    
    # Test with fixed amount
    print("\nUsing fixed amount ($10):")
    for symbol, price in test_symbols_prices:
        quantity = checker.get_safe_trade_amount(symbol, price, use_percentage=False, fixed_amount=10.0)
        print(f"{symbol} @ ${price:,.2f}: {quantity} units (${quantity * price:,.2f})")
    
    # Test with percentage
    print("\nUsing percentage (1%):")
    for symbol, price in test_symbols_prices:
        quantity = checker.get_safe_trade_amount(symbol, price, use_percentage=True, percentage=1.0)
        print(f"{symbol} @ ${price:,.2f}: {quantity} units (${quantity * price:,.2f})")
    
    print("\nBalance checker test completed successfully!")

if __name__ == "__main__":
    test_balance_checker() 