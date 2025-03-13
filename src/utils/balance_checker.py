import os
import json
import redis
from datetime import datetime

class BalanceChecker:
    """Utility for checking account balance before executing trades."""
    
    def __init__(self, redis_client=None):
        """Initialize the balance checker with a Redis client."""
        if redis_client:
            self.redis_client = redis_client
        else:
            # Initialize Redis connection
            redis_host = os.getenv('REDIS_HOST', 'redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))
            self.redis_client = redis.Redis(
                host=redis_host, port=redis_port, db=redis_db, decode_responses=True
            )
        
        # Minimum account balance to maintain as buffer
        self.min_balance_buffer = float(os.getenv('MIN_BALANCE_BUFFER', '50.0'))
        
        # Default mock balance to use if real balance retrieval fails
        self.default_mock_balance = 10000.0
    
    def get_account_data(self):
        """Retrieve account data from Redis or create mock data if missing."""
        try:
            account_key = "account:data"
            account_data = self.redis_client.get(account_key)
            
            if account_data:
                return json.loads(account_data)
            else:
                # Create mock account data if none exists
                self._create_mock_account()
                return self._get_mock_account()
        except Exception as e:
            print(f"Error getting account data: {e}")
            return self._get_mock_account()
    
    def _create_mock_account(self):
        """Create mock account data in Redis if real account data is missing."""
        mock_account = {
            "account_number": "PA12345",
            "cash": self.default_mock_balance,
            "portfolio_value": self.default_mock_balance,
            "buying_power": self.default_mock_balance,
            "equity": self.default_mock_balance,
            "paper_trading": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "positions": [],
            "daily_change": 0.00,
            "daily_change_percent": 0.00,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Save account data to Redis
            self.redis_client.set("account:data", json.dumps(mock_account))
            print(f"Created mock account with ${self.default_mock_balance:,.2f} balance")
        except Exception as e:
            print(f"Error creating mock account: {e}")
    
    def _get_mock_account(self):
        """Return a mock account data dictionary."""
        return {
            "account_number": "PA12345",
            "cash": self.default_mock_balance,
            "portfolio_value": self.default_mock_balance,
            "buying_power": self.default_mock_balance,
            "equity": self.default_mock_balance,
            "paper_trading": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "positions": [],
            "daily_change": 0.00,
            "daily_change_percent": 0.00
        }
    
    def has_sufficient_balance(self, amount_needed, currency="USD"):
        """
        Check if there's sufficient balance for a trade.
        
        Args:
            amount_needed: Float amount needed for the trade
            currency: Currency code (default: USD)
            
        Returns:
            (bool, float): Tuple of (has_sufficient_balance, available_balance)
        """
        try:
            account_data = self.get_account_data()
            
            # Get available balance (use buying_power for USD)
            available_balance = account_data.get("buying_power", 0)
            if currency != "USD":
                # For other currencies, check positions
                positions = account_data.get("positions", [])
                for position in positions:
                    if position.get("symbol") == currency:
                        available_balance = float(position.get("qty", 0))
                        break
            
            # Check if balance has buffer amount plus the amount needed
            has_sufficient = available_balance >= (amount_needed + self.min_balance_buffer)
            
            return has_sufficient, available_balance
        except Exception as e:
            print(f"Error checking balance: {e}")
            # Assume sufficient balance if we can't check
            return True, self.default_mock_balance
    
    def get_safe_trade_amount(self, symbol, price, use_percentage=False, percentage=1.0, fixed_amount=10.0):
        """
        Calculate a safe trade amount that won't exceed available balance.
        
        Args:
            symbol: Trading symbol
            price: Current price of the asset
            use_percentage: Whether to use percentage or fixed amount
            percentage: Percentage of portfolio to use (0-100)
            fixed_amount: Fixed amount to trade
            
        Returns:
            float: Safe trade amount in quantity
        """
        try:
            account_data = self.get_account_data()
            available_balance = float(account_data.get("buying_power", 0))
            
            # Apply a safety buffer
            available_balance = max(0, available_balance - self.min_balance_buffer)
            
            if available_balance <= 0:
                return 0.0
            
            if use_percentage:
                # Convert percentage to decimal (e.g., 1% -> 0.01)
                percent_decimal = max(0.1, min(100, percentage)) / 100
                trade_amount = available_balance * percent_decimal
            else:
                # Use fixed amount but cap at available balance
                trade_amount = min(fixed_amount, available_balance)
            
            # Calculate quantity based on price
            if price and price > 0:
                quantity = trade_amount / price
                
                # Round quantity to appropriate decimal places based on price
                if price >= 1000:
                    quantity = round(quantity, 6)  # Very expensive assets
                elif price >= 100:
                    quantity = round(quantity, 5)
                elif price >= 10:
                    quantity = round(quantity, 4)
                elif price >= 1:
                    quantity = round(quantity, 3)
                else:
                    quantity = round(quantity, 2)
                
                return quantity
            else:
                return 0.0
        except Exception as e:
            print(f"Error calculating safe trade amount: {e}")
            return 0.1  # Return minimal amount as fallback 