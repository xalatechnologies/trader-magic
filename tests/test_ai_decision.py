import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai_decision.service import AIDecisionService
from src.utils.models import RSIData, TradeSignal, TradingDecision


class TestAIDecisionService(unittest.TestCase):
    
    def setUp(self):
        # Create a test instance of the service
        self.service = AIDecisionService()
        
        # Create a test RSI data object
        self.rsi_data = RSIData(
            symbol="BTC/USD",
            value=25.5,  # Low RSI value that should trigger a buy
            timestamp=datetime.now()
        )
    
    @patch('src.ai_decision.ollama_client.ollama_client.generate')
    def test_analyze_rsi_buy(self, mock_generate):
        # Mock the ollama_client.generate method
        mock_generate.return_value = asyncio.Future()
        mock_generate.return_value.set_result("Based on the RSI value of 25.5, I recommend to buy.")
        
        # Call the method
        result = asyncio.run(self.service.analyze_rsi(self.rsi_data))
        
        # Verify the response
        self.assertIsInstance(result, TradeSignal)
        self.assertEqual(result.symbol, "BTC/USD")
        self.assertEqual(result.decision, TradingDecision.BUY)
        self.assertEqual(result.rsi_value, 25.5)
        
        # Verify ollama_client.generate was called with the correct arguments
        mock_generate.assert_called_once()
    
    @patch('src.ai_decision.ollama_client.ollama_client.generate')
    def test_analyze_rsi_sell(self, mock_generate):
        # Mock the ollama_client.generate method to return a sell decision
        mock_generate.return_value = asyncio.Future()
        mock_generate.return_value.set_result("sell")
        
        # Set RSI value to indicate overbought condition
        self.rsi_data.value = 75.5
        
        # Call the method
        result = asyncio.run(self.service.analyze_rsi(self.rsi_data))
        
        # Verify the response
        self.assertEqual(result.decision, TradingDecision.SELL)
    
    @patch('src.ai_decision.ollama_client.ollama_client.generate')
    def test_analyze_rsi_hold(self, mock_generate):
        # Mock the ollama_client.generate method to return a hold decision
        mock_generate.return_value = asyncio.Future()
        mock_generate.return_value.set_result("Based on the RSI value, I would hold.")
        
        # Set RSI value to neutral range
        self.rsi_data.value = 50.0
        
        # Call the method
        result = asyncio.run(self.service.analyze_rsi(self.rsi_data))
        
        # Verify the response
        self.assertEqual(result.decision, TradingDecision.HOLD)
    
    @patch('src.ai_decision.ollama_client.ollama_client.generate')
    def test_analyze_rsi_error(self, mock_generate):
        # Mock the ollama_client.generate method to raise an exception
        mock_generate.side_effect = Exception("API Error")
        
        # Call the method
        result = asyncio.run(self.service.analyze_rsi(self.rsi_data))
        
        # Verify the response is None
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()