import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_retrieval.taapi_client import TaapiClient
from src.utils.models import RSIData

class TestTaapiClient(unittest.TestCase):
    
    @patch('requests.get')
    def test_get_rsi_success(self, mock_get):
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": 42.5}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Create client with test API key
        client = TaapiClient()
        client.api_key = "test_api_key"
        
        # Call the method
        result = client.get_rsi("BTC/USD")
        
        # Verify the response
        self.assertIsInstance(result, RSIData)
        self.assertEqual(result.symbol, "BTC/USD")
        self.assertEqual(result.value, 42.5)
        
        # Verify the API was called with correct parameters
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://api.taapi.io/rsi")
        self.assertEqual(kwargs['params']['symbol'], "BTC/USD")
        self.assertEqual(kwargs['params']['secret'], "test_api_key")
    
    @patch('requests.get')
    def test_get_rsi_error(self, mock_get):
        # Mock the response to raise an exception
        mock_get.side_effect = Exception("API Error")
        
        # Create client with test API key
        client = TaapiClient()
        client.api_key = "test_api_key"
        
        # Call the method and expect an exception
        with self.assertRaises(Exception):
            client.get_rsi("BTC/USD")
            
if __name__ == '__main__':
    unittest.main()