from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.trading.client import TradingClient
from alpaca.data.requests import StockBarsRequest, NewsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus
from datetime import datetime, timedelta
import config
import pandas as pd

class AlpacaClient:
    def __init__(self):
        self.data_client = StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)
        self.news_client = NewsClient(config.API_KEY, config.SECRET_KEY)
        self.trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

    def _retry_request(self, method, *args, **kwargs):
        """Internal helper to retry requests on connection failure with exponential backoff."""
        max_retries = 5 # Increased from 3
        import time
        import random
        
        for attempt in range(max_retries):
            try:
                return method(*args, **kwargs)
            except Exception as e:
                # Check for connection-related errors
                error_msg = str(e).lower()
                is_connection_error = any(kw in error_msg for kw in ["connection", "500", "502", "503", "504", "timeout", "getaddrinfo", "dns", "11001", "temporary failure", "ssl", "protocol"])
                
                if is_connection_error:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2, 4, 8, 16, 32...
                        # Add jitter (+/- 10%) to prevent synchronized retries
                        base_sleep = 2 * (2 ** attempt)
                        jitter = base_sleep * 0.1 * (random.random() * 2 - 1)
                        sleep_time = max(1, base_sleep + jitter)
                        
                        print(f"⚠️ Connection/DNS Error: {e}. Retrying in {sleep_time:.1f}s... ({attempt+1}/{max_retries})")
                        time.sleep(sleep_time)
                        continue
                
                # If we're here, it's either not a connection error or we hit max retries
                if attempt == max_retries - 1:
                    print(f"❌ Max retries reached for request: {e}")
                raise e # Re-raise if not temporary or max retries hit

    def get_account(self):
        return self._retry_request(self.trading_client.get_account)

    def get_historical_data(self, symbol: str, lookback_days: int = 180):
        """Fetches historical daily data for multi-day trading strategy."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,  # Changed to daily bars for multi-day trading
            start=start_time,
            end=end_time
        )
        
        def fetch():
            bars = self.data_client.get_stock_bars(request)
            return bars.df if not bars.df.empty else pd.DataFrame()
            
            return bars.df if not bars.df.empty else pd.DataFrame()
            
        return self._retry_request(fetch)

    def get_company_news(self, symbol: str, lookback_days: int = 3):
        """Fetches recent news headlines for a symbol."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)
        
        request = NewsRequest(
            symbols=symbol,
            start=start_time,
            end=end_time,
            limit=10 # Top 10 headlines is enough for sentiment
        )
        
        def fetch():
            # Returns a list of News objects
            return self.news_client.get_news(request)
            
        return self._retry_request(fetch)

    def get_latest_quote(self, symbol: str):
        """Fetches the latest snapshot (including Bid/Ask) for a symbol."""
        request = StockSnapshotRequest(symbol_or_symbols=symbol)
        
        def fetch():
            snapshots = self.data_client.get_stock_snapshot(request)
            if symbol in snapshots:
                s = snapshots[symbol]
                bid = s.latest_quote.bid_price
                ask = s.latest_quote.ask_price
                return {
                    'bid': bid,
                    'ask': ask,
                    'last': s.latest_trade.price,
                    'spread_pct': (ask - bid) / (bid + 1e-6) if bid > 0 else 0
                }
            return None
            
        return self._retry_request(fetch)
    
    def get_snapshots(self, symbols: list):
        """Fetches latest snapshots for a list of symbols in batches."""
        if not symbols: return {}
        
        all_snapshots = {}
        batch_size = 50 # Safe size to avoid long URLs
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            request = StockSnapshotRequest(symbol_or_symbols=batch)
            
            def fetch():
                return self.data_client.get_stock_snapshot(request)
            
            try:
                batch_res = self._retry_request(fetch)
                all_snapshots.update(batch_res)
            except Exception as e:
                print(f"  ⚠️ Failed to fetch snapshots for batch {i//batch_size + 1}: {e}")
                
        return all_snapshots

    def get_asset(self, symbol: str):
        """Fetches asset details (shortable, easy_to_borrow, etc)."""
        return self._retry_request(self.trading_client.get_asset, symbol_or_asset_id=symbol)

    def submit_order(self, symbol: str, qty: int, side: str, limit_price: float = None):
        """Submits an order. Uses Limit Order if price is provided, else Market Order."""
        
        # Robust Side Handling
        if isinstance(side, str):
            side = side.lower().strip()
            
        final_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL
        print(f"  [Alpaca] Submitting {final_side} order for {qty} {symbol} (Limit: {limit_price})")

        if limit_price:
            # Alpaca Tick Size Rules:
            # Price >= $1.00: 2 decimal places
            # Price < $1.00: 4 decimal places
            if limit_price >= 1.0:
                limit_price = round(limit_price, 2)
            else:
                limit_price = round(limit_price, 4)
                
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=final_side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price
            )
        else:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=final_side,
                time_in_force=TimeInForce.DAY
            )
        
        return self._retry_request(self.trading_client.submit_order, order_data=order_data)

    def get_positions(self):
        return self._retry_request(self.trading_client.get_all_positions)
    
    def get_open_orders(self, symbol: str = None):
        """Get open orders, optionally filtered by symbol."""
        try:
            if symbol:
                request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            else:
                request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            return self._retry_request(self.trading_client.get_orders, filter=request_params)
        except Exception as e:
            print(f"Error fetching open orders: {e}")
            return []

    def close_position(self, symbol: str):
        """Closes all positions for a symbol. Cancels open orders first to release held shares."""
        try:
            # 1. Cancel open orders for this symbol to release 'held_for_orders' qty
            # Note: client.cancel_orders() cancels ALL. We must verify specific symbol first.
            request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            open_orders = self.trading_client.get_orders(filter=request_params)
            
            for order in open_orders:
                print(f"  [Alpaca] Cancelling open order {order.id} for {symbol}")
                self.trading_client.cancel_order_by_id(order.id)
            
            # 2. Close position
            self._retry_request(self.trading_client.close_position, symbol)
        except Exception as e:
            print(f"Error closing position for {symbol}: {e}")
