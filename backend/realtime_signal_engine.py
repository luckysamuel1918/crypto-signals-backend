import asyncio
import time
from typing import Dict, Optional
from datetime import datetime
from backend.signals import analyze_timeframe, calculate_ema, calculate_rsi, calculate_atr, get_ohlcv_data, send_telegram_message
from backend.websocket_manager import WebSocketPriceManager
from backend.pre_signal_predictor import PreSignalPredictor

class RealtimeSignalEngine:
    def __init__(self, ws_manager: WebSocketPriceManager, execution_manager=None, signal_lead_time: int = 30):
        self.ws_manager = ws_manager
        self.execution_manager = execution_manager
        self.active_signals: Dict[str, Dict] = {}
        self.last_indicators: Dict[str, Dict] = {}
        self.indicator_update_interval = 60  # Update indicators every 60 seconds
        self.last_indicator_update: Dict[str, float] = {}
        
        # Pre-signal prediction system
        self.predictor = PreSignalPredictor(signal_lead_time=signal_lead_time)
        self.signal_lead_time = signal_lead_time
        
    async def start_monitoring(self, symbol: str, timeframe: str = "1hour"):
        """
        Start real-time monitoring for a symbol
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            timeframe: Primary timeframe for analysis
        """
        symbol = symbol.upper()
        
        # Initial indicator calculation
        await self._update_indicators(symbol, timeframe)
        
        # Subscribe to WebSocket price updates
        await self.ws_manager.subscribe(
            symbol,
            lambda s, p, t: asyncio.create_task(self._handle_price_update(s, p, t, timeframe))
        )
        
        # Start periodic indicator updates
        asyncio.create_task(self._periodic_indicator_update(symbol, timeframe))
        
        print(f"📊 Started real-time monitoring for {symbol}")
        
    async def _periodic_indicator_update(self, symbol: str, timeframe: str):
        """Periodically update indicators every minute"""
        while True:
            try:
                await asyncio.sleep(self.indicator_update_interval)
                await self._update_indicators(symbol, timeframe)
            except Exception as e:
                print(f"❌ Error in periodic indicator update for {symbol}: {e}")
                await asyncio.sleep(self.indicator_update_interval)
                
    async def _update_indicators(self, symbol: str, timeframe: str):
        """Update technical indicators for a symbol"""
        try:
            print(f"🔄 Updating indicators for {symbol}...")
            
            # Analyze multiple timeframes in parallel
            timeframes = ["15min", "1hour", "4hour"]
            tasks = [
                asyncio.to_thread(analyze_timeframe, symbol, tf)
                for tf in timeframes
            ]
            analyses = await asyncio.gather(*tasks)
            
            # Create analysis dict
            valid_analyses = {}
            for i, tf in enumerate(timeframes):
                if "error" not in analyses[i]:
                    valid_analyses[tf] = analyses[i]
                    
            if len(valid_analyses) < 2:
                print(f"⚠️ Insufficient data for {symbol}")
                return
                
            # Use primary timeframe for indicators
            primary_tf = "1hour" if "1hour" in valid_analyses else list(valid_analyses.keys())[0]
            primary_data = valid_analyses[primary_tf]
            
            # Count bullish/bearish timeframes
            bullish_count = sum(1 for data in valid_analyses.values() if data["trend"] == "BULLISH")
            bearish_count = sum(1 for data in valid_analyses.values() if data["trend"] == "BEARISH")
            total_timeframes = len(valid_analyses)
            confidence = max(bullish_count, bearish_count) / total_timeframes
            
            # Store indicators
            self.last_indicators[symbol] = {
                "ema12": primary_data["ema12"],
                "ema26": primary_data["ema26"],
                "rsi": primary_data["rsi"],
                "atr": primary_data["atr"],
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "total_timeframes": total_timeframes,
                "confidence": confidence,
                "last_candle_close": primary_data["current_price"],
                "updated_at": time.time()
            }
            
            self.last_indicator_update[symbol] = time.time()
            
            print(f"✅ Indicators updated for {symbol}: EMA12={primary_data['ema12']:.2f}, EMA26={primary_data['ema26']:.2f}, RSI={primary_data['rsi']:.2f}")
            
            # Add data point to pre-signal predictor
            self.predictor.add_data_point(
                symbol=symbol,
                price=primary_data["current_price"],
                rsi=primary_data["rsi"],
                ema12=primary_data["ema12"],
                ema26=primary_data["ema26"]
            )
            
        except Exception as e:
            print(f"❌ Error updating indicators for {symbol}: {e}")
            
    async def _handle_price_update(self, symbol: str, price: float, exchange_timestamp: int, timeframe: str):
        """
        Handle real-time price update and check for signal generation
        
        Args:
            symbol: Trading pair
            price: Current price
            exchange_timestamp: Exchange server timestamp (milliseconds)
            timeframe: Primary timeframe
        """
        try:
            # Check if we have indicators for this symbol
            if symbol not in self.last_indicators:
                return
                
            indicators = self.last_indicators[symbol]
            
            # Get current local time
            local_timestamp = int(time.time() * 1000)
            
            # Calculate delay between exchange time and local time
            delay_ms = abs(local_timestamp - exchange_timestamp)
            delay_seconds = delay_ms / 1000
            
            # Log price update (throttled)
            if symbol not in self.active_signals or time.time() - self.active_signals.get(symbol, {}).get("last_log", 0) > 10:
                print(f"💰 {symbol}: ${price:,.2f} | Delay: {delay_seconds:.2f}s")
                if symbol not in self.active_signals:
                    self.active_signals[symbol] = {}
                self.active_signals[symbol]["last_log"] = time.time()
            
            # CRITICAL: Skip if delay > 2 seconds
            if delay_seconds > 2.0:
                print(f"⏭️ {symbol} - Signal delayed ({delay_seconds:.2f}s > 2s) — skipped to prevent slippage")
                return
                
            # Check for signal conditions
            ema12 = indicators["ema12"]
            ema26 = indicators["ema26"]
            rsi = indicators["rsi"]
            confidence = indicators["confidence"]
            last_candle_close = indicators["last_candle_close"]
            
            # ====================================================================
            # PRE-SIGNAL PREDICTION: Alert 20-60 seconds before signal triggers
            # ====================================================================
            
            # Add current price data point to predictor
            self.predictor.add_data_point(
                symbol=symbol,
                price=price,
                rsi=rsi,
                ema12=ema12,
                ema26=ema26
            )
            
            # Check if a signal is about to trigger
            pre_signal = self.predictor.predict_signal(
                symbol=symbol,
                current_price=price,
                ema12=ema12,
                ema26=ema26,
                rsi=rsi,
                confidence=confidence
            )
            
            if pre_signal:
                await self._send_pre_signal_alert(pre_signal)
            
            # ====================================================================
            # ACTUAL SIGNAL DETECTION (existing logic)
            # ====================================================================
            
            # Determine signal
            signal = None
            entry_price = last_candle_close  # Use last candle close as baseline entry
            
            # BUY Signal: EMA12 > EMA26 and RSI > 50
            if ema12 > ema26 and rsi > 50:
                signal = "BUY"
                
            # SELL Signal: EMA12 < EMA26 and RSI < 50
            elif ema12 < ema26 and rsi < 50:
                signal = "SELL"
                
            if signal:
                # Check if this is a new signal (not already active)
                active_signal = self.active_signals.get(symbol, {}).get("signal")
                
                if active_signal != signal:
                    # New signal detected!
                    print(f"\n{'='*60}")
                    print(f"🚨 NEW {signal} SIGNAL DETECTED: {symbol}")
                    print(f"{'='*60}")
                    
                    # Calculate price difference from entry
                    price_diff_pct = ((price - entry_price) / entry_price) * 100
                    
                    # Check if current price is within ±0.2% of entry price
                    if abs(price_diff_pct) <= 0.2:
                        # Price is good - prepare signal for execution
                        signal_data = {
                            "symbol": symbol,
                            "signal": signal,
                            "entry_price": entry_price,
                            "current_live_price": price,
                            "price_diff_pct": price_diff_pct,
                            "ema12": ema12,
                            "ema26": ema26,
                            "rsi": rsi,
                            "confidence": confidence,
                            "exchange_timestamp": exchange_timestamp,
                            "local_timestamp": local_timestamp,
                            "delay_seconds": delay_seconds,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "EXECUTE"
                        }
                        
                        # Store active signal
                        self.active_signals[symbol] = {
                            "signal": signal,
                            "entry_price": entry_price,
                            "generated_at": time.time()
                        }
                        
                        # Mark signal triggered for pre-signal accuracy tracking
                        self.predictor.mark_signal_triggered(symbol, signal)
                        
                        print(f"✅ Price within tolerance: {price:,.2f} ({price_diff_pct:+.3f}% from entry)")
                        print(f"⏱️ Delay: {delay_seconds:.2f}s (< 2s threshold)")
                        print(f"📊 Indicators: EMA12={ema12:.2f}, EMA26={ema26:.2f}, RSI={rsi:.2f}")
                        print(f"🎯 Confidence: {confidence:.2%} ({indicators['bullish_count' if signal == 'BUY' else 'bearish_count']}/{indicators['total_timeframes']} timeframes)")
                        
                        # Execute signal immediately
                        if self.execution_manager:
                            try:
                                await self.execution_manager.execute_signal(signal_data)
                            except Exception as e:
                                print(f"❌ Execution error: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print("⚠️ No execution manager configured - signal detected but not executed")
                        
                        return signal_data
                        
                    else:
                        # Price moved too much - adjust or skip
                        signal_data = {
                            "symbol": symbol,
                            "signal": signal,
                            "entry_price": entry_price,
                            "current_live_price": price,
                            "price_diff_pct": price_diff_pct,
                            "ema12": ema12,
                            "ema26": ema26,
                            "rsi": rsi,
                            "confidence": confidence,
                            "exchange_timestamp": exchange_timestamp,
                            "local_timestamp": local_timestamp,
                            "delay_seconds": delay_seconds,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "ADJUST_ENTRY"
                        }
                        
                        # Adjust entry price to current live price
                        adjusted_entry = price
                        
                        # Store active signal with adjusted entry
                        self.active_signals[symbol] = {
                            "signal": signal,
                            "entry_price": adjusted_entry,
                            "generated_at": time.time()
                        }
                        
                        # Mark signal triggered for pre-signal accuracy tracking
                        self.predictor.mark_signal_triggered(symbol, signal)
                        
                        print(f"⚠️ Price moved {price_diff_pct:+.3f}% from entry (> ±0.2% tolerance)")
                        print(f"🔄 Entry price adjusted: ${entry_price:,.2f} → ${adjusted_entry:,.2f}")
                        print(f"✅ Signal prepared with adjusted entry")
                        
                        signal_data["entry_price"] = adjusted_entry
                        signal_data["adjusted"] = True
                        
                        # Execute adjusted signal immediately
                        if self.execution_manager:
                            try:
                                await self.execution_manager.execute_signal(signal_data)
                            except Exception as e:
                                print(f"❌ Execution error: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print("⚠️ No execution manager configured - signal detected but not executed")
                        
                        return signal_data
                        
        except Exception as e:
            print(f"❌ Error handling price update for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            
    async def _send_pre_signal_alert(self, pre_signal: Dict):
        """Send pre-signal alert to Telegram"""
        try:
            symbol = pre_signal["symbol"]
            predicted_signal = pre_signal["predicted_signal"]
            expected_entry = pre_signal["expected_entry"]
            estimated_time = pre_signal["estimated_time_seconds"]
            confidence = pre_signal["confidence"]
            current_price = pre_signal["current_price"]
            rsi = pre_signal["rsi"]
            ema12 = pre_signal["ema12"]
            ema26 = pre_signal["ema26"]
            
            # Signal emoji
            signal_emoji = {
                "BUY": "🟢",
                "SELL": "🔴"
            }.get(predicted_signal, "⚪")
            
            # Build pre-signal message
            message = f"🚨 **Pre-Signal Alert**\n"
            message += f"⚡ *{predicted_signal} Signal Approaching*\n\n"
            message += f"Pair: {symbol}\n"
            message += f"Current Price: ${current_price:,.2f}\n"
            message += f"Expected Entry: ${expected_entry:,.2f}\n"
            message += f"Estimated Hit Time: ~{estimated_time}s\n"
            message += f"Signal: {signal_emoji} **{predicted_signal}**\n"
            message += f"Confidence: {confidence:.0%}\n\n"
            message += f"📊 Indicators:\n"
            message += f"RSI: {rsi:.1f} | EMA12: {ema12:,.2f} | EMA26: {ema26:,.2f}\n\n"
            message += f"⏰ Prepare to execute trade in ~{estimated_time} seconds\n"
            message += f"📍 Time: {pre_signal['timestamp']}"
            
            # Send via Telegram
            send_telegram_message(message)
            
            print(f"\n{'='*60}")
            print(f"⚡ PRE-SIGNAL ALERT SENT: {symbol}")
            print(f"{'='*60}")
            print(f"📋 PRE-SIGNAL DETAILS:")
            print(f"   Predicted Signal: {predicted_signal}")
            print(f"   Current Price: ${current_price:,.2f}")
            print(f"   Expected Entry: ${expected_entry:,.2f}")
            print(f"   Estimated Time: ~{estimated_time}s")
            print(f"   Confidence: {confidence:.0%}")
            print(f"   RSI: {rsi:.1f} | EMA12: {ema12:,.2f} | EMA26: {ema26:,.2f}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error sending pre-signal alert: {e}")
            import traceback
            traceback.print_exc()
    
    def get_active_signals(self) -> Dict[str, Dict]:
        """Get all active signals"""
        return self.active_signals
        
    def clear_signal(self, symbol: str):
        """Clear active signal for a symbol"""
        if symbol in self.active_signals:
            del self.active_signals[symbol]
            print(f"🗑️ Cleared active signal for {symbol}")
            
    def get_prediction_stats(self) -> Dict:
        """Get pre-signal prediction accuracy statistics"""
        return self.predictor.get_prediction_stats()
        
    def set_signal_lead_time(self, seconds: int):
        """Update the signal lead time for pre-signal alerts"""
        self.signal_lead_time = seconds
        self.predictor.signal_lead_time = seconds
        print(f"✅ Signal lead time updated to {seconds} seconds")
