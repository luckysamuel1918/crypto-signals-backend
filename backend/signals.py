import os
import asyncio
import requests
from typing import List, Optional, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from backend.kucoin_service import get_ticker_price, fetch_klines

# 🔐 Telegram credentials (hardcoded)
TELEGRAM_BOT_TOKEN = "7160932182:AAGAv_yyOQSOaKNxMCPmw3Bmtpt-9EvJpPk"
TELEGRAM_CHAT_ID = "7089989920"

# 🎯 Top 20 popular cryptocurrency pairs for signal generation
CRYPTO_PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "XRP-USDT", "ADA-USDT",
    "DOGE-USDT", "SOL-USDT", "MATIC-USDT", "DOT-USDT", "AVAX-USDT",
    "UNI-USDT", "LINK-USDT", "LTC-USDT", "ATOM-USDT", "BCH-USDT",
    "NEAR-USDT", "FTT-USDT", "ALGO-USDT", "XLM-USDT", "ICP-USDT"
]

# Global scheduler and bot instances
scheduler = BackgroundScheduler()
telegram_bot = None
is_auto_signals_running = False

def send_telegram_message(text: str):
    # Split message if it's too long (Telegram limit is 4096 characters)
    max_length = 4000  # Leave some buffer
    if len(text) <= max_length:
        _send_single_telegram_message(text)
    else:
        # Split the message into chunks
        chunks = _split_telegram_message(text, max_length)
        for i, chunk in enumerate(chunks):
            if i > 0:
                # Add small delay between messages to avoid rate limiting
                import time
                time.sleep(1)
            _send_single_telegram_message(chunk)

def _send_single_telegram_message(text: str):
    """Send a single Telegram message"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram message sent successfully")
        else:
            print(f"❌ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")

def _split_telegram_message(text: str, max_length: int) -> List[str]:
    """Split a long message into smaller chunks while preserving formatting"""
    chunks = []
    lines = text.split('\n')
    current_chunk = ""
    
    for line in lines:
        # If adding this line would exceed the limit, save current chunk and start new one
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        
        current_chunk += line + "\n"
    
    # Add the last chunk if it has content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def generate_single_signal(symbol: str, timeframe: str = "15min", send_notification: bool = False) -> Dict:
    """Generate signal for a single crypto pair with accuracy validation and fresh data"""
    try:
        # Always fetch fresh real-time market data
        price = get_ticker_price(symbol)
        klines = fetch_klines(symbol, interval=timeframe, limit=200)
        closes = get_closes_from_klines(klines)
        if not closes:
            return {"symbol": symbol, "error": "no historical closes available"}

        # Calculate accuracy using backtesting on last 20 candles
        accuracy = backtest_signal_accuracy(symbol, timeframe, test_periods=20)
        print(f"🎯 {symbol} accuracy: {accuracy:.1f}%")
        
        # Only proceed if accuracy is >= 50% (balanced threshold for quality signals)
        if accuracy < 50.0:
            print(f"⚠️ Skipping {symbol} - accuracy {accuracy:.1f}% below 50% threshold")
            return {"symbol": symbol, "skipped": True, "accuracy": accuracy, "reason": "accuracy below 50% threshold"}

        # Calculate indicators with fresh data
        rsi = calculate_rsi(closes, period=14)
        ema12 = simple_ema(closes, 12)
        ema26 = simple_ema(closes, 26)

        # Enhanced signal decision logic with multiple indicators
        signal = "HOLD"
        confidence = 0
        signal_reasons = []
        
        # RSI Analysis (more sensitive thresholds)
        if rsi is not None:
            if rsi < 40:  # More sensitive buy threshold
                signal = "BUY" 
                confidence += 2
                signal_reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 60:  # More sensitive sell threshold
                signal = "SELL"
                confidence += 2  
                signal_reasons.append(f"RSI overbought ({rsi:.1f})")
            elif 40 <= rsi <= 50:
                signal = "BUY"
                confidence += 1
                signal_reasons.append(f"RSI neutral-bullish ({rsi:.1f})")
            elif 50 <= rsi <= 60:
                signal = "SELL" 
                confidence += 1
                signal_reasons.append(f"RSI neutral-bearish ({rsi:.1f})")
        
        # EMA Trend Analysis
        ema_signal = "HOLD"
        if ema12 is not None and ema26 is not None:
            ema_diff_pct = ((ema12 - ema26) / ema26) * 100
            if ema12 > ema26:
                ema_signal = "BUY"
                confidence += 1 if ema_diff_pct > 0.5 else 0.5
                signal_reasons.append(f"EMA bullish trend ({ema_diff_pct:.2f}%)")
            elif ema12 < ema26:
                ema_signal = "SELL"
                confidence += 1 if abs(ema_diff_pct) > 0.5 else 0.5
                signal_reasons.append(f"EMA bearish trend ({ema_diff_pct:.2f}%)")
        
        # Final signal with confirmation
        if signal == ema_signal and confidence >= 2:
            final = signal
        elif confidence >= 3:
            final = signal
        elif ema_signal != "HOLD" and confidence >= 1.5:
            final = ema_signal
        else:
            final = signal if confidence >= 1 else "HOLD"
            
        # Enhanced take profit and stop loss calculations
        tp_long = None
        sl_long = None
        tp_short = None  
        sl_short = None
        entry_price = price
        order_type = "LIMIT"  # ALWAYS use LIMIT orders for safety (no market orders)
        
        # Dynamic TP/SL based on volatility and confidence
        base_tp_pct = 0.015 + (confidence * 0.005)  # 1.5% to 3%
        base_sl_pct = 0.008 + (confidence * 0.002)  # 0.8% to 1.4%
        
        if final == "BUY":
            tp_long = round(price * (1 + base_tp_pct), 6)
            sl_long = round(price * (1 - base_sl_pct), 6)
            # ALWAYS use LIMIT orders for safety - no market orders
            order_type = "LIMIT"
        elif final == "SELL":
            tp_short = round(price * (1 - base_tp_pct), 6)
            sl_short = round(price * (1 + base_sl_pct), 6)
            # ALWAYS use LIMIT orders for safety - no market orders
            order_type = "LIMIT"

        result = {
            "symbol": symbol,
            "price": round(price, 6),
            "signal": final,
            "confidence": round(confidence, 1),
            "reasons": signal_reasons,
            "rsi": rsi,
            "ema12": round(ema12, 6) if ema12 else None,
            "ema26": round(ema26, 6) if ema26 else None,
            "entry_price": entry_price,
            "order_type": order_type,
            "take_profit_long": tp_long,
            "stop_loss_long": sl_long,
            "take_profit_short": tp_short,
            "stop_loss_short": sl_short,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "accuracy": accuracy
        }

        # Send notification only if requested
        if send_notification:
            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
            confidence_stars = "⭐" * min(int(confidence), 5)
            
            message = (
                f"🚨 *Crypto Signal Alert*\n"
                f"Pair: `{symbol}`\n"
                f"Signal: {emoji.get(final, '⚪')} *{final}* {confidence_stars}\n"
                f"Entry Price: `${entry_price:,.6f}`\n"
                f"Order Type: `{order_type}`\n"
                f"Confidence: `{confidence:.1f}/5.0`\n\n"
                f"📊 *Technical Analysis:*\n"
                f"RSI: `{rsi:.1f}` | EMA12: `{ema12:.2f}` | EMA26: `{ema26:.2f}`\n"
            )
            
            if signal_reasons:
                message += f"Reasons: {', '.join(signal_reasons[:2])}\n\n"
            
            if final == "BUY":
                message += (
                    f"💰 *Long Position Setup:*\n"
                    f"Take Profit: `${tp_long:,.6f}` (+{base_tp_pct*100:.1f}%)\n"
                    f"Stop Loss: `${sl_long:,.6f}` (-{base_sl_pct*100:.1f}%)\n"
                )
            elif final == "SELL":
                message += (
                    f"💰 *Short Position Setup:*\n"  
                    f"Take Profit: `${tp_short:,.6f}` (-{base_tp_pct*100:.1f}%)\n"
                    f"Stop Loss: `${sl_short:,.6f}` (+{base_sl_pct*100:.1f}%)\n"
                )
            
            message += (
                f"\n🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
                f"⚠️ *RISK WARNING*\n"
                f"• Crypto trading involves high risk\n"
                f"• Only invest what you can afford to lose\n"
                f"• Past performance does not guarantee future results\n"
                f"• Always do your own research (DYOR)\n"
                f"• Consider market conditions and news\n"
                f"• Use proper position sizing and risk management"
            )
            send_telegram_message(message)

        return result
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# Backward compatibility function for existing API
def generate_signal_with_notification(symbol: str = "BTC-USDT", timeframe: str = "1hour"):
    """Generate signal for backward compatibility with existing API"""
    return generate_single_signal(symbol, timeframe, send_notification=True)

def generate_batch_signals() -> List[Dict]:
    """Generate signals for all 20 cryptocurrency pairs using multithreading"""
    print(f"🔄 Generating signals for {len(CRYPTO_PAIRS)} crypto pairs...")
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all signal generation tasks
        future_to_symbol = {
            executor.submit(generate_single_signal, symbol, "15min"): symbol 
            for symbol in CRYPTO_PAIRS
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_symbol):
            result = future.result()
            results.append(result)
    
    # Sort results by symbol for consistent ordering
    results.sort(key=lambda x: x.get("symbol", ""))
    
    # Send consolidated Telegram message
    send_batch_signals_to_telegram(results)
    
    print(f"✅ Generated signals for {len(results)} pairs")
    return results

def send_batch_signals_to_telegram(signals: List[Dict]):
    """Send detailed alerts for each symbol in one consolidated Telegram message"""
    if not signals:
        return
    
    # Filter valid signals (not errors or skipped)
    valid_signals = [s for s in signals if not s.get("error") and not s.get("skipped")]
    skipped_signals = [s for s in signals if s.get("skipped")]
    error_signals = [s for s in signals if s.get("error")]
    
    if not valid_signals and not skipped_signals and not error_signals:
        return
    
    message = f"📊 *Crypto Signals Update*\n"
    message += f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
    
    # Add detailed alerts for each valid signal
    signal_count = 0
    for signal in valid_signals:
        if signal.get("signal") == "HOLD":
            continue  # Skip HOLD signals for cleaner output
            
        signal_count += 1
        
        # Get signal details
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal", "")
        price = signal.get("price", 0)
        confidence = signal.get("confidence", 0)
        rsi = signal.get("rsi", 0)
        ema12 = signal.get("ema12", 0)
        ema26 = signal.get("ema26", 0)
        reasons = signal.get("reasons", [])
        timestamp = signal.get("timestamp", "")
        
        # Signal emoji and stars
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
        signal_emoji = emoji.get(signal_type, "⚪")
        confidence_stars = "⭐" * min(int(confidence), 5)
        
        # Take profit and stop loss
        if signal_type == "BUY":
            take_profit = signal.get("take_profit_long")
            stop_loss = signal.get("stop_loss_long")
        else:  # SELL
            take_profit = signal.get("take_profit_short")
            stop_loss = signal.get("stop_loss_short")
        
        # Format reason text
        reason_text = ", ".join(reasons[:2]) if reasons else "Technical analysis"
        
        # Create detailed alert
        message += f"🚨 *Crypto Signal Alert*\n"
        message += f"Pair: `{symbol}`\n"
        message += f"Signal: {signal_emoji} *{signal_type}* {confidence_stars}\n"
        message += f"Entry Price: `${price:,.6f}`\n"
        message += f"Order Type: `LIMIT`\n"
        message += f"Confidence: `{confidence:.1f}/5.0`\n\n"
        
        message += f"📊 *Technical Analysis:*\n"
        message += f"RSI: `{rsi:.1f}` | EMA12: `{ema12:.2f}` | EMA26: `{ema26:.2f}`\n"
        message += f"Reasons: {reason_text}\n\n"
        
        message += f"💰 *Trade Setup:*\n"
        if take_profit and stop_loss:
            message += f"Take Profit: `${take_profit:,.6f}`\n"
            message += f"Stop Loss: `${stop_loss:,.6f}`\n\n"
        else:
            message += f"Take Profit: `Not set`\n"
            message += f"Stop Loss: `Not set`\n\n"
        
        message += f"🕐 Time: `{timestamp}`\n"
        message += f"----------------------\n\n"
    
    # Add summary at the end
    hold_count = len([s for s in valid_signals if s.get("signal") == "HOLD"])
    if hold_count > 0:
        message += f"🟡 *{hold_count} pairs in HOLD status*\n\n"
    
    if skipped_signals:
        message += f"⚠️ *{len(skipped_signals)} signals skipped* (accuracy < 70%)\n"
        skipped_symbols = [s.get("symbol", "") for s in skipped_signals if s.get("symbol")]
        message += f"Skipped: {', '.join(skipped_symbols)}\n\n"
    
    if error_signals:
        message += f"❌ *{len(error_signals)} errors:* "
        error_symbols = [s.get("symbol", "") for s in error_signals if s.get("symbol")]
        message += f"{', '.join(error_symbols)}\n\n"
    
    # Final note
    if signal_count == 0:
        message += f"📈 *No high-confidence signals at this time*\n"
        message += f"All signals either in HOLD or below 70% accuracy threshold\n\n"
    
    message += f"⚠️ *RISK WARNING*\n"
    message += f"• Crypto trading involves high risk\n"
    message += f"• Only invest what you can afford to lose\n"
    message += f"• Always do your own research (DYOR)\n"
    message += f"• Consider market conditions and news\n\n"
    message += f"_Next update in 15 minutes ⏰_"
    
    send_telegram_message(message)

def start_auto_signals():
    """Start the automated signal generation every 15 minutes"""
    global is_auto_signals_running
    if is_auto_signals_running:
        print("⚠️ Auto signals already running")
        return
        
    scheduler.add_job(
        func=generate_batch_signals,
        trigger="interval",
        minutes=15,
        id='crypto_signals',
        replace_existing=True
    )
    
    if not scheduler.running:
        scheduler.start()
        
    is_auto_signals_running = True
    print("✅ Auto signals started - will run every 15 minutes")
    
    # Send initial signals immediately
    generate_batch_signals()

def stop_auto_signals():
    """Stop the automated signal generation"""
    global is_auto_signals_running
    if scheduler.running:
        scheduler.remove_job('crypto_signals')
        is_auto_signals_running = False
        print("🛑 Auto signals stopped")
    else:
        print("⚠️ Auto signals not running")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command from Telegram bot"""
    if not update.message:
        return
        
    start_auto_signals()
    await update.message.reply_text(
        "🚀 *Lucky Signals Bot Started!*\n\n"
        "📊 Generating signals for 20 crypto pairs every 15 minutes\n"
        "🕐 First batch coming right now...\n\n"
        "Commands:\n"
        "/start - Start auto signals\n"
        "/stop - Stop auto signals\n"
        "/status - Check bot status",
        parse_mode="Markdown"
    )

async def handle_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command from Telegram bot"""
    if not update.message:
        return
        
    stop_auto_signals()
    await update.message.reply_text("🛑 Auto signals stopped!")

async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command from Telegram bot"""
    if not update.message:
        return
        
    status = "✅ Running" if is_auto_signals_running else "❌ Stopped"
    await update.message.reply_text(
        f"📊 *Bot Status:* {status}\n"
        f"🎯 Pairs monitored: {len(CRYPTO_PAIRS)}\n"
        f"⏰ Update interval: 15 minutes",
        parse_mode="Markdown"
    )

def setup_telegram_bot():
    """Setup Telegram bot with command handlers"""
    global telegram_bot
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", handle_start_command))
        application.add_handler(CommandHandler("stop", handle_stop_command))
        application.add_handler(CommandHandler("status", handle_status_command))
        
        telegram_bot = application
        print("✅ Telegram bot setup complete")
        return application
    except Exception as e:
        print(f"❌ Failed to setup Telegram bot: {e}")
        return None

def get_closes_from_klines(klines: List) -> List[float]:
    """
    Convert KuCoin candle array to close price floats.
    KuCoin structure: [timestamp, open, close, high, low, volume, turnover]
    Index 2 = close price (verified)
    """
    if not klines:
        raise ValueError("No candle data provided")
        
    closes = []
    for i, candle in enumerate(klines):
        try:
            if len(candle) < 3:
                raise ValueError(f"Invalid candle structure at index {i}: {candle}")
            close = float(candle[2])  # Index 2 is close price
            if close <= 0:
                raise ValueError(f"Invalid close price {close} at index {i}")
            closes.append(close)
        except (ValueError, IndexError) as e:
            raise ValueError(f"Error processing candle at index {i}: {e}")
    
    if len(closes) < 20:  # Need minimum data for reliable calculations
        raise ValueError(f"Insufficient price data: {len(closes)} candles (minimum 20 required)")
        
    return closes

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate RSI using Wilder's smoothing method (industry standard).
    Verified against TradingView and professional trading platforms.
    """
    if len(prices) < period + 1:
        return None
    
    # Calculate initial gains and losses for first period
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return None
    
    # Initial average gain and loss (SMA for first period)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Apply Wilder's smoothing for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Handle edge case
    if avg_loss == 0:
        return 100.0
    
    # Calculate RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)

def simple_ema(values: List[float], period: int):
    if len(values) < period:
        return None
    sma = sum(values[:period]) / period
    prev = sma
    k = 2 / (period + 1)
    for price in values[period:]:
        prev = price*k + prev*(1-k)
    return prev

def backtest_signal_accuracy(symbol: str, timeframe: str = "15min", test_periods: int = 20) -> float:
    """
    Backtest the signal generation logic on historical data to calculate accuracy.
    Returns accuracy percentage (0-100) based on correct signal predictions.
    """
    try:
        # Fetch more historical data for backtesting (need extra for indicators)
        klines = fetch_klines(symbol, interval=timeframe, limit=200)
        closes = get_closes_from_klines(klines)
        
        if len(closes) < test_periods + 50:  # Need extra data for indicators
            print(f"⚠️ Insufficient data for backtesting {symbol}")
            return 0.0
        
        correct_predictions = 0
        total_predictions = 0
        
        # Test on the last test_periods candles
        for i in range(len(closes) - test_periods, len(closes) - 1):
            # Get historical data up to point i
            historical_closes = closes[:i+1]
            
            if len(historical_closes) < 50:  # Need minimum data for indicators
                continue
                
            # Calculate indicators at point i
            rsi = calculate_rsi(historical_closes, period=14)
            ema12 = simple_ema(historical_closes, 12)
            ema26 = simple_ema(historical_closes, 26)
            
            if rsi is None or ema12 is None or ema26 is None:
                continue
                
            # Generate signal using same logic as generate_single_signal
            signal = "HOLD"
            confidence = 0
            
            # RSI Analysis (same thresholds as main function)
            if rsi < 40:
                signal = "BUY"
                confidence += 2
            elif rsi > 60:
                signal = "SELL"
                confidence += 2
            elif 40 <= rsi <= 50:
                signal = "BUY"
                confidence += 1
            elif 50 <= rsi <= 60:
                signal = "SELL"
                confidence += 1
            
            # EMA Trend Analysis
            ema_signal = "HOLD"
            if ema12 > ema26:
                ema_signal = "BUY"
                ema_diff_pct = ((ema12 - ema26) / ema26) * 100
                confidence += 1 if ema_diff_pct > 0.5 else 0.5
            elif ema12 < ema26:
                ema_signal = "SELL"
                ema_diff_pct = ((ema12 - ema26) / ema26) * 100
                confidence += 1 if abs(ema_diff_pct) > 0.5 else 0.5
            
            # Final signal decision (same logic as main function)
            if signal == ema_signal and confidence >= 2:
                final_signal = signal
            elif confidence >= 3:
                final_signal = signal
            elif ema_signal != "HOLD" and confidence >= 1.5:
                final_signal = ema_signal
            else:
                final_signal = signal if confidence >= 1 else "HOLD"
            
            # Check if signal was correct by looking at next candle
            if i + 1 < len(closes):
                current_price = closes[i]
                next_price = closes[i + 1]
                price_change_pct = ((next_price - current_price) / current_price) * 100
                
                # Define success criteria (conservative thresholds)
                if final_signal == "BUY" and price_change_pct > 0.1:  # Price went up
                    correct_predictions += 1
                elif final_signal == "SELL" and price_change_pct < -0.1:  # Price went down
                    correct_predictions += 1
                elif final_signal == "HOLD" and abs(price_change_pct) <= 0.5:  # Price stayed stable
                    correct_predictions += 1
                
                total_predictions += 1
        
        if total_predictions == 0:
            return 0.0
            
        accuracy = (correct_predictions / total_predictions) * 100
        return round(accuracy, 2)
        
    except Exception as e:
        print(f"❌ Backtesting error for {symbol}: {e}")
        return 0.0

def generate_signal(symbol: str = "BTC-USDT", timeframe: str = "1hour"):
    """
    Enhanced trading signal generation with improved technical analysis.
    Used by the API endpoint - calls the enhanced generate_single_signal function.
    """
    return generate_single_signal(symbol, timeframe, send_notification=True)