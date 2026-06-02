
import unittest
from unittest.mock import MagicMock, ANY
from trading.alpaca_client import AlpacaClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

class TestSmartExecution(unittest.TestCase):
    def setUp(self):
        self.client = AlpacaClient()
        self.client.trading_client = MagicMock()

    def test_submit_limit_order(self):
        """Verify that passing limit_price creates a LimitOrderRequest"""
        symbol = 'AAPL'
        qty = 10
        price = 150.0
        
        # Call with limit price
        self.client.submit_order(symbol, qty, 'buy', limit_price=price)
        
        # Assert submit_order was called
        self.client.trading_client.submit_order.assert_called_once()
        
        # Capture args
        call_args = self.client.trading_client.submit_order.call_args
        order_request = call_args.kwargs['order_data']
        
        # Verify it is a Limit Order
        self.assertIsInstance(order_request, LimitOrderRequest)
        self.assertEqual(order_request.limit_price, price)
        self.assertEqual(order_request.symbol, symbol)
        print(f"✅ Verified Limit Order created for {symbol} at ${price}")

    def test_submit_market_order_fallback(self):
        """Verify that omitting limit_price still creates a MarketOrderRequest"""
        self.client.submit_order('AAPL', 10, 'buy')
        
        call_args = self.client.trading_client.submit_order.call_args
        order_request = call_args.kwargs['order_data']
        
        self.assertIsInstance(order_request, MarketOrderRequest)
        print(f"✅ Verified Market Order created (fallback)")

if __name__ == '__main__':
    unittest.main()
