"""
KuCoin API Client Wrapper
Supports both sandbox (paper trading) and production (live trading) modes
"""

from kucoin.client import Trade, Market, User
from typing import Optional, Dict, Literal
import os
from datetime import datetime

class KuCoinClient:
    """
    KuCoin trading client with support for both sandbox and live trading
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        mode: Literal["sandbox", "live"] = "sandbox"
    ):
        """
        Initialize KuCoin client
        
        Args:
            api_key: KuCoin API key
            api_secret: KuCoin API secret
            api_passphrase: KuCoin API passphrase
            mode: "sandbox" for paper trading or "live" for real trading
        """
        self.mode = mode
        
        # Get credentials from environment if not provided
        self.api_key = api_key or os.getenv("KUCOIN_API_KEY")
        self.api_secret = api_secret or os.getenv("KUCOIN_API_SECRET")
        self.api_passphrase = api_passphrase or os.getenv("KUCOIN_API_PASSPHRASE")
        
        # Set the API endpoint based on mode
        if mode == "sandbox":
            self.base_url = "https://openapi-sandbox.kucoin.com"
            print("🧪 KuCoin Client: SANDBOX MODE (Paper Trading)")
        else:
            self.base_url = "https://api.kucoin.com"
            print("💰 KuCoin Client: LIVE MODE (Real Trading)")
        
        # Initialize clients
        self.trade_client = None
        self.market_client = None
        self.user_client = None
        
        if self.api_key and self.api_secret and self.api_passphrase:
            self._initialize_clients()
        else:
            print("⚠️ KuCoin credentials not provided - trading disabled")
    
    def _initialize_clients(self):
        """Initialize KuCoin API clients"""
        try:
            # Trading client (requires authentication)
            self.trade_client = Trade(
                key=self.api_key,
                secret=self.api_secret,
                passphrase=self.api_passphrase,
                url=self.base_url
            )
            
            # Market client (public endpoints)
            self.market_client = Market(url=self.base_url)
            
            # User client (account info)
            self.user_client = User(
                key=self.api_key,
                secret=self.api_secret,
                passphrase=self.api_passphrase,
                url=self.base_url
            )
            
            print(f"✅ KuCoin clients initialized successfully ({self.mode} mode)")
        except Exception as e:
            print(f"❌ Failed to initialize KuCoin clients: {e}")
            raise
    
    def is_configured(self) -> bool:
        """Check if client is properly configured"""
        return self.trade_client is not None
    
    def get_account_balance(self, currency: str = "USDT") -> float:
        """
        Get account balance for a specific currency
        
        Args:
            currency: Currency symbol (e.g., "USDT", "BTC")
        
        Returns:
            Available balance
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            accounts = self.user_client.get_account_list(currency=currency, account_type="trade")
            
            if accounts and len(accounts) > 0:
                balance = float(accounts[0].get("available", 0))
                print(f"💰 {currency} Balance: {balance}")
                return balance
            return 0.0
        except Exception as e:
            print(f"❌ Error getting balance: {e}")
            return 0.0
    
    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
        
        Returns:
            Current price
        """
        try:
            ticker = self.market_client.get_ticker(symbol)
            price = float(ticker.get("price", 0))
            return price
        except Exception as e:
            print(f"❌ Error getting price for {symbol}: {e}")
            return 0.0
    
    def place_market_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        size: Optional[float] = None,
        funds: Optional[float] = None
    ) -> Dict:
        """
        Place a market order
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "buy" or "sell"
            size: Order size (amount of base currency)
            funds: Order funds (amount of quote currency, for buy orders)
        
        Returns:
            Order response dict with orderId
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            if side == "buy" and funds:
                # Market buy using funds (quote currency)
                result = self.trade_client.create_market_order(
                    symbol=symbol,
                    side=side,
                    funds=str(funds)
                )
            elif size:
                # Market order using size (base currency)
                result = self.trade_client.create_market_order(
                    symbol=symbol,
                    side=side,
                    size=str(size)
                )
            else:
                raise ValueError("Must provide either size or funds")
            
            print(f"✅ Market {side.upper()} order placed: {symbol}")
            return result
        except Exception as e:
            print(f"❌ Error placing market order: {e}")
            raise
    
    def place_limit_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        price: float,
        size: float
    ) -> Dict:
        """
        Place a limit order
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "buy" or "sell"
            price: Limit price
            size: Order size
        
        Returns:
            Order response dict with orderId
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            result = self.trade_client.create_limit_order(
                symbol=symbol,
                side=side,
                price=str(price),
                size=str(size)
            )
            
            print(f"✅ Limit {side.upper()} order placed: {symbol} @ ${price}")
            return result
        except Exception as e:
            print(f"❌ Error placing limit order: {e}")
            raise
    
    def place_stop_loss_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        stop_price: float,
        size: float,
        limit_price: Optional[float] = None
    ) -> Dict:
        """
        Place a stop-loss order
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "buy" or "sell"
            stop_price: Stop trigger price
            size: Order size
            limit_price: Optional limit price (if None, uses market order)
        
        Returns:
            Order response dict with orderId
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            if limit_price:
                # Stop-limit order
                result = self.trade_client.create_limit_order(
                    symbol=symbol,
                    side=side,
                    price=str(limit_price),
                    size=str(size),
                    stop=str(stop_price),
                    stop_price=str(stop_price)
                )
            else:
                # Stop-market order
                result = self.trade_client.create_market_order(
                    symbol=symbol,
                    side=side,
                    size=str(size),
                    stop=str(stop_price),
                    stop_price=str(stop_price)
                )
            
            print(f"✅ Stop-loss {side.upper()} order placed: {symbol} @ stop ${stop_price}")
            return result
        except Exception as e:
            print(f"❌ Error placing stop-loss order: {e}")
            raise
    
    def execute_trade_with_protection(
        self,
        symbol: str,
        signal_type: Literal["BUY", "SELL"],
        entry_price: float,
        take_profit: float,
        stop_loss: float,
        order_size_usdt: float = 10.0
    ) -> Dict:
        """
        Execute a complete trade with entry, take profit, and stop loss
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            signal_type: "BUY" or "SELL"
            entry_price: Entry price
            take_profit: Take profit price
            stop_loss: Stop loss price
            order_size_usdt: Order size in USDT (default: $10)
        
        Returns:
            Dict with order IDs and execution details
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "KuCoin client not configured",
                "message": "Please set up your KuCoin API credentials"
            }
        
        try:
            side = "buy" if signal_type == "BUY" else "sell"
            
            # Calculate order size based on entry price
            current_price = self.get_current_price(symbol)
            order_size = order_size_usdt / current_price
            
            print(f"\n{'='*60}")
            print(f"🚀 EXECUTING TRADE: {signal_type} {symbol}")
            print(f"{'='*60}")
            print(f"Entry Price: ${entry_price:,.2f}")
            print(f"Current Price: ${current_price:,.2f}")
            print(f"Order Size: {order_size:.6f} ({symbol.split('-')[0]})")
            print(f"Order Value: ${order_size_usdt:.2f}")
            print(f"Take Profit: ${take_profit:,.2f}")
            print(f"Stop Loss: ${stop_loss:,.2f}")
            print(f"Mode: {self.mode.upper()}")
            print(f"{'='*60}\n")
            
            # 1. Place entry order (market order for immediate execution)
            entry_order = self.place_market_order(
                symbol=symbol,
                side=side,
                funds=order_size_usdt if side == "buy" else None,
                size=order_size if side == "sell" else None
            )
            
            # 2. Place take profit order (limit order on opposite side)
            tp_side = "sell" if signal_type == "BUY" else "buy"
            take_profit_order = self.place_limit_order(
                symbol=symbol,
                side=tp_side,
                price=take_profit,
                size=order_size
            )
            
            # 3. Place stop loss order (stop order on opposite side)
            stop_loss_order = self.place_stop_loss_order(
                symbol=symbol,
                side=tp_side,
                stop_price=stop_loss,
                size=order_size
            )
            
            result = {
                "success": True,
                "symbol": symbol,
                "signal_type": signal_type,
                "mode": self.mode,
                "entry_order_id": entry_order.get("orderId"),
                "take_profit_order_id": take_profit_order.get("orderId"),
                "stop_loss_order_id": stop_loss_order.get("orderId"),
                "entry_price": entry_price,
                "current_price": current_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "order_size": order_size,
                "order_value_usdt": order_size_usdt,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Trade executed successfully in {self.mode} mode"
            }
            
            print(f"✅ Trade executed successfully!")
            print(f"Entry Order ID: {entry_order.get('orderId')}")
            print(f"Take Profit Order ID: {take_profit_order.get('orderId')}")
            print(f"Stop Loss Order ID: {stop_loss_order.get('orderId')}")
            print(f"{'='*60}\n")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Trade execution failed: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "symbol": symbol,
                "signal_type": signal_type,
                "mode": self.mode,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Trade execution failed: {error_msg}"
            }
    
    def get_order_status(self, order_id: str) -> Dict:
        """
        Get status of an order
        
        Args:
            order_id: Order ID to check
        
        Returns:
            Order details
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            return self.trade_client.get_order_details(order_id)
        except Exception as e:
            print(f"❌ Error getting order status: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation response
        """
        if not self.is_configured():
            raise Exception("KuCoin client not configured")
        
        try:
            result = self.trade_client.cancel_order(order_id)
            print(f"✅ Order {order_id} cancelled")
            return result
        except Exception as e:
            print(f"❌ Error cancelling order: {e}")
            raise
