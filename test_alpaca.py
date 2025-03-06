"""
Test script to diagnose Alpaca API connection issues.
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print environment variables (mask sensitive parts)
api_key = os.getenv("APCA_API_KEY_ID", "")
api_secret = os.getenv("APCA_API_SECRET_KEY", "")
print(f"APCA_API_KEY_ID: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
print(f"APCA_API_SECRET_KEY: {api_secret[:4]}...{api_secret[-4:] if len(api_secret) > 8 else ''}")

# Try direct REST API call
base_url = "https://paper-api.alpaca.markets"
endpoint = f"{base_url}/v2/account"
headers = {
    "APCA-API-KEY-ID": api_key,
    "APCA-API-SECRET-KEY": api_secret
}

print(f"\nTesting direct REST API call to: {endpoint}")
try:
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        account = response.json()
        print(f"SUCCESS! Account ID: {account.get('id')}")
        print(f"Account status: {account.get('status')}")
        print(f"Buying power: ${float(account.get('buying_power', 0)):.2f}")
    else:
        print(f"ERROR! Status code: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Exception: {e}")

# Test with alternative API URL
base_url = "https://api.alpaca.markets"
endpoint = f"{base_url}/v2/account" 
print(f"\nTesting with alternative URL: {endpoint}")
try:
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        account = response.json()
        print(f"SUCCESS! Account ID: {account.get('id')}")
        print(f"Account status: {account.get('status')}")
        print(f"Buying power: ${float(account.get('buying_power', 0)):.2f}")
    else:
        print(f"ERROR! Status code: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Exception: {e}")