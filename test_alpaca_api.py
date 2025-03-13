import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment
api_key = os.getenv("ALPACA_API_KEY")
api_secret = os.getenv("ALPACA_API_SECRET")
base_url = os.getenv("APCA_API_BASE_URL")

print(f"API Key: {api_key[:4]}...{api_key[-4:]}")
print(f"API Secret: {api_secret[:4]}...{api_secret[-4:]}")
print(f"Base URL: {base_url}")

# Create the client
try:
    client = TradingClient(
        api_key=api_key,
        secret_key=api_secret,
        paper=True
    )
    
    # Get account info
    account = client.get_account()
    print(f"Connection successful!")
    print(f"Account status: {account.status}")
    print(f"Account cash: ${float(account.cash):.2f}")
    print(f"Account portfolio value: ${float(account.portfolio_value):.2f}")
    
except Exception as e:
    print(f"Error connecting to Alpaca API: {e}") 