"""
Trade Execution Service
Handles automated trade execution based on signals
"""

from backend.kucoin_client import KuCoinClient
from backend.signals import send_telegram_message
from typing import Dict, Literal, Optional
from datetime import datetime

class TradeExecutor:
    """
    Service to execute trades automatically based on signals
    """
    
    def __init__(
        self,
        kucoin_client: Optional[KuCoinClient] = None,
        auto_execute: bool = False,
        order_size_usdt: float = 10.0
    ):
        """
        Initialize trade executor
        
        Args:
            kucoin_client: KuCoin client instance
            auto_execute: Whether to automatically execute trades
            order_size_usdt: Default order size in USDT
        """
        self.kucoin_client = kucoin_client
        self.auto_execute = auto_execute
        self.order_size_usdt = order_size_usdt
        self.execution_history = []
        
        print(f"⚡ Trade Executor initialized")
        print(f"   Auto-execute: {'ENABLED' if auto_execute else 'DISABLED'}")
        print(f"   Order size: ${order_size_usdt} USDT")
        if kucoin_client and kucoin_client.is_configured():
            print(f"   Mode: {kucoin_client.mode.upper()}")
    
    def set_auto_execute(self, enabled: bool):
        """Enable or disable auto-execution"""
        self.auto_execute = enabled
        status = "ENABLED" if enabled else "DISABLED"
        print(f"⚡ Auto-execution {status}")
    
    def set_order_size(self, size_usdt: float):
        """Set order size in USDT"""
        self.order_size_usdt = size_usdt
        print(f"💰 Order size set to ${size_usdt} USDT")
    
    def execute_signal(
        self,
        signal_data: Dict,
        force: bool = False
    ) -> Dict:
        """
        Execute a trade based on signal data
        
        Args:
            signal_data: Signal dict from generate_signal()
            force: Force execution even if auto_execute is disabled
        
        Returns:
            Execution result dict
        """
        # Check if execution is enabled
        if not self.auto_execute and not force:
            return {
                "success": False,
                "error": "Auto-execution is disabled",
                "message": "Enable auto-trading to execute signals automatically"
            }
        
        # Check if KuCoin client is configured
        if not self.kucoin_client or not self.kucoin_client.is_configured():
            return {
                "success": False,
                "error": "KuCoin not configured",
                "message": "Please set up your KuCoin API credentials"
            }
        
        # Extract signal data
        symbol = signal_data.get("symbol")
        signal_type = signal_data.get("signal")
        entry_price = signal_data.get("entry_price") or signal_data.get("entry")
        take_profit = signal_data.get("take_profit")
        stop_loss = signal_data.get("stop_loss")
        confidence = signal_data.get("confidence", 0)
        
        # Validate signal
        if signal_type not in ["BUY", "SELL"]:
            return {
                "success": False,
                "error": "Invalid signal type",
                "message": f"Signal type must be BUY or SELL, got {signal_type}"
            }
        
        if not all([entry_price, take_profit, stop_loss]):
            return {
                "success": False,
                "error": "Missing price data",
                "message": "Signal must include entry_price, take_profit, and stop_loss"
            }
        
        # Execute trade
        try:
            result = self.kucoin_client.execute_trade_with_protection(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=entry_price,
                take_profit=take_profit,
                stop_loss=stop_loss,
                order_size_usdt=self.order_size_usdt
            )
            
            # Add signal data to result
            result["confidence"] = confidence
            result["manual_request"] = signal_data.get("manual_request", False)
            
            # Store in history
            self.execution_history.append(result)
            
            # Send Telegram notification
            self._send_execution_notification(result, signal_data)
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "signal_type": signal_type,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Execution failed: {str(e)}"
            }
            
            # Send error notification
            self._send_execution_notification(error_result, signal_data)
            
            return error_result
    
    def _send_execution_notification(self, execution_result: Dict, signal_data: Dict):
        """Send Telegram notification about trade execution"""
        try:
            if execution_result.get("success"):
                # Success message
                symbol = execution_result.get("symbol")
                signal_type = execution_result.get("signal_type")
                mode = execution_result.get("mode", "unknown").upper()
                entry_order_id = execution_result.get("entry_order_id")
                tp_order_id = execution_result.get("take_profit_order_id")
                sl_order_id = execution_result.get("stop_loss_order_id")
                entry_price = execution_result.get("entry_price")
                current_price = execution_result.get("current_price")
                take_profit = execution_result.get("take_profit")
                stop_loss = execution_result.get("stop_loss")
                order_value = execution_result.get("order_value_usdt")
                confidence = execution_result.get("confidence", 0)
                
                signal_emoji = "🟢" if signal_type == "BUY" else "🔴"
                mode_emoji = "🧪" if mode == "SANDBOX" else "💰"
                
                message = f"✅ {mode_emoji} TRADE EXECUTED ({mode})\n\n"
                message += f"{signal_emoji} {signal_type} {symbol}\n"
                message += f"💵 Order Value: ${order_value:.2f}\n"
                message += f"📊 Confidence: {confidence*100:.0f}%\n\n"
                message += f"📈 Entry: ${entry_price:,.2f}\n"
                message += f"💰 Current: ${current_price:,.2f}\n"
                message += f"🎯 Take Profit: ${take_profit:,.2f}\n"
                message += f"🛡️ Stop Loss: ${stop_loss:,.2f}\n\n"
                message += f"🆔 Entry Order: {entry_order_id}\n"
                message += f"🆔 TP Order: {tp_order_id}\n"
                message += f"🆔 SL Order: {sl_order_id}\n"
                
            else:
                # Error message
                symbol = execution_result.get("symbol", "Unknown")
                signal_type = execution_result.get("signal_type", "Unknown")
                error = execution_result.get("error", "Unknown error")
                
                message = f"❌ TRADE EXECUTION FAILED\n\n"
                message += f"Signal: {signal_type} {symbol}\n"
                message += f"Error: {error}\n\n"
                message += "Please check your KuCoin API configuration."
            
            # Send message
            send_telegram_message(message)
            
        except Exception as e:
            print(f"❌ Failed to send execution notification: {e}")
    
    def get_execution_history(self, limit: int = 10) -> list:
        """Get recent execution history"""
        return self.execution_history[-limit:]
    
    def clear_execution_history(self):
        """Clear execution history"""
        self.execution_history = []
        print("🗑️ Execution history cleared")
