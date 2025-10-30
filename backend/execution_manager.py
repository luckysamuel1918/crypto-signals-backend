import asyncio
from typing import Dict, Optional
from datetime import datetime
from backend.signals import send_telegram_message
import json

class ExecutionManager:
    def __init__(self):
        self.execution_log = []
        self.max_log_size = 100
        
    async def execute_signal(self, signal_data: Dict) -> Dict:
        """
        Execute a trading signal with comprehensive logging
        
        Args:
            signal_data: Signal data from RealtimeSignalEngine
            
        Returns:
            Execution result with status and details
        """
        try:
            symbol = signal_data["symbol"]
            signal = signal_data["signal"]
            action = signal_data.get("action", "EXECUTE")
            
            print(f"\n{'='*60}")
            print(f"⚡ EXECUTING {signal} SIGNAL: {symbol}")
            print(f"{'='*60}")
            
            # Calculate take profit and stop loss
            entry_price = signal_data["entry_price"]
            
            if signal == "BUY":
                take_profit = round(entry_price * 1.015, 6)  # +1.5%
                stop_loss = round(entry_price * 0.99, 6)  # -1%
                tp_pct = 1.5
                sl_pct = -1.0
            elif signal == "SELL":
                take_profit = round(entry_price * 0.985, 6)  # -1.5%
                stop_loss = round(entry_price * 1.01, 6)  # +1%
                tp_pct = -1.5
                sl_pct = 1.0
            else:
                take_profit = None
                stop_loss = None
                tp_pct = 0
                sl_pct = 0
                
            # Prepare execution log entry
            execution_entry = {
                "timestamp": signal_data["timestamp"],
                "symbol": symbol,
                "signal": signal,
                "action": action,
                "entry_price": entry_price,
                "current_live_price": signal_data["current_live_price"],
                "price_diff_pct": signal_data["price_diff_pct"],
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "ema12": signal_data["ema12"],
                "ema26": signal_data["ema26"],
                "rsi": signal_data["rsi"],
                "confidence": signal_data["confidence"],
                "delay_seconds": signal_data["delay_seconds"],
                "exchange_timestamp": signal_data["exchange_timestamp"],
                "local_timestamp": signal_data["local_timestamp"],
                "adjusted": signal_data.get("adjusted", False),
                "status": "EXECUTED"
            }
            
            # Log execution details
            print(f"📋 EXECUTION DETAILS:")
            print(f"   Timestamp: {execution_entry['timestamp']}")
            print(f"   Signal Type: {signal}")
            print(f"   Action: {action}")
            print(f"   Entry Price: ${entry_price:,.2f}")
            print(f"   Current Live Price: ${signal_data['current_live_price']:,.2f}")
            print(f"   Price Difference: {signal_data['price_diff_pct']:+.3f}%")
            print(f"   Take Profit: ${take_profit:,.2f} ({tp_pct:+.1f}%)")
            print(f"   Stop Loss: ${stop_loss:,.2f} ({sl_pct:+.1f}%)")
            print(f"   Indicators: EMA12={signal_data['ema12']:.2f}, EMA26={signal_data['ema26']:.2f}, RSI={signal_data['rsi']:.2f}")
            print(f"   Confidence: {signal_data['confidence']:.2%}")
            print(f"   Signal Delay: {signal_data['delay_seconds']:.2f}s")
            print(f"   Exchange Time: {datetime.fromtimestamp(signal_data['exchange_timestamp']/1000).strftime('%H:%M:%S.%f')[:-3]}")
            print(f"   Local Time: {datetime.fromtimestamp(signal_data['local_timestamp']/1000).strftime('%H:%M:%S.%f')[:-3]}")
            
            if execution_entry["adjusted"]:
                print(f"   ⚠️ Entry price was adjusted to match live market")
                
            # Store in execution log
            self.execution_log.append(execution_entry)
            
            # Trim log if too large
            if len(self.execution_log) > self.max_log_size:
                self.execution_log = self.execution_log[-self.max_log_size:]
                
            # Send Telegram notification
            await self._send_telegram_notification(execution_entry)
            
            print(f"✅ EXECUTION COMPLETED: {symbol} {signal}")
            print(f"{'='*60}\n")
            
            return {
                "status": "success",
                "execution": execution_entry
            }
            
        except Exception as e:
            error_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": signal_data.get("symbol", "Unknown"),
                "error": str(e),
                "status": "FAILED"
            }
            
            self.execution_log.append(error_entry)
            
            print(f"❌ EXECUTION FAILED: {str(e)}")
            print(f"{'='*60}\n")
            
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _send_telegram_notification(self, execution: Dict):
        """Send execution notification to Telegram"""
        try:
            symbol = execution["symbol"]
            signal = execution["signal"]
            action = execution["action"]
            
            # Signal emoji
            signal_emoji = {
                "BUY": "🟢",
                "SELL": "🔴",
                "HOLD": "🟡"
            }.get(signal, "⚪")
            
            # Action status
            action_status = {
                "EXECUTE": "✅ EXECUTED",
                "ADJUST_ENTRY": "🔄 EXECUTED (Entry Adjusted)",
                "SKIP": "⏭️ SKIPPED"
            }.get(action, "❓ UNKNOWN")
            
            # Order type emoji
            order_type = execution.get("order_type", "N/A")
            order_emoji = "⚡" if order_type == "MARKET" else "📋"
            entry_time_source = execution.get("entry_time_source", "N/A")
            slippage_used = execution.get("slippage_used", 0)
            
            # Build message with NEW METADATA
            message = f"🚨 **Real-Time Signal Alert**\n"
            message += f"Status: {action_status}\n"
            message += f"Pair: {symbol}\n"
            message += f"Signal: {signal_emoji} **{signal}**\n"
            message += f"Entry: ${execution['entry_price']:,.2f}\n"
            message += f"Order Type: {order_emoji} {order_type}\n"
            message += f"Entry Source: {entry_time_source}\n"
            message += f"Slippage: {slippage_used:.4f}%\n"
            message += f"Live Price: ${execution['current_live_price']:,.2f} ({execution['price_diff_pct']:+.3f}%)\n"
            
            if execution["take_profit"] and execution["stop_loss"]:
                message += f"Take Profit: ${execution['take_profit']:,.2f} ({execution['tp_pct']:+.1f}%)\n"
                message += f"Stop Loss: ${execution['stop_loss']:,.2f} ({execution['sl_pct']:+.1f}%)\n"
            else:
                message += f"Take Profit: N/A\n"
                message += f"Stop Loss: N/A\n"
                
            message += f"RSI: {execution['rsi']:.1f} | EMA12: {execution['ema12']:,.2f} | EMA26: {execution['ema26']:,.2f}\n"
            message += f"Confidence: {execution['confidence']:.0%}\n"
            message += f"Delay: {execution['delay_seconds']:.2f}s\n"
            message += f"Time: {execution['timestamp']}\n"
            
            if execution.get("adjusted"):
                message += f"\n⚠️ Entry price adjusted to match live market"
                
            # Send via existing Telegram function
            send_telegram_message(message)
            
            print(f"📤 Telegram notification sent for {symbol} {signal}")
            
        except Exception as e:
            print(f"❌ Failed to send Telegram notification: {e}")
            
    def get_execution_log(self, limit: int = 10) -> list:
        """Get recent execution log entries"""
        return self.execution_log[-limit:]
        
    def get_log_summary(self) -> Dict:
        """Get summary of execution log"""
        total = len(self.execution_log)
        successful = sum(1 for e in self.execution_log if e.get("status") == "EXECUTED")
        failed = sum(1 for e in self.execution_log if e.get("status") == "FAILED")
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0
        }
        
    def export_log(self, filepath: str = "execution_log.json"):
        """Export execution log to JSON file"""
        try:
            with open(filepath, "w") as f:
                json.dump(self.execution_log, f, indent=2)
            print(f"✅ Execution log exported to {filepath}")
        except Exception as e:
            print(f"❌ Failed to export log: {e}")
