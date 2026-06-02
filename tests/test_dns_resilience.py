import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import socket

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.alpaca_client import AlpacaClient

class TestDNSResilience(unittest.TestCase):
    
    def test_dns_retry_logic(self):
        """Test that client retries on DNS (getaddrinfo) errors."""
        client = AlpacaClient()
        
        # Mocking a method to simulate a DNS failure
        # Alpaca's StockBarsRequest usually triggers network calls.
        # We'll mock the internal _retry_request's target method to raise gaierror.
        
        mock_method = MagicMock(side_effect=[
            socket.gaierror(11001, 'getaddrinfo failed'),
            socket.gaierror(11001, 'getaddrinfo failed'),
            "Success"
        ])
        
        with patch('time.sleep') as mock_sleep:
            # We call _retry_request directly to test its logic
            result = client._retry_request(mock_method)
            
            # Should have called mock_method 3 times (2 failures + 1 success)
            self.assertEqual(mock_method.call_count, 3)
            # Should have slept twice
            self.assertEqual(mock_sleep.call_count, 2)
            # Result should be success
            self.assertEqual(result, "Success")
            
            # Verify exponential backoff (2s, 4s...)
            # Note: Jitter means it won't be EXACTLY 2.0 and 4.0
            sleep_args = [call.args[0] for call in mock_sleep.call_args_list]
            self.assertTrue(1.5 <= sleep_args[0] <= 2.5) # ~2s
            self.assertTrue(3.5 <= sleep_args[1] <= 4.5) # ~4s

if __name__ == '__main__':
    unittest.main()
