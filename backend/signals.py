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

# 🔐 Hardcoded Telegram credentials
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Missing Telegram credentials")
        return
    
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

def generate_single_signal(symbol: str, timeframe: str = "15min", send_notification: bool = False) -> Dict:
    """Generate signal for a single crypto pair without sending notification by default"""
    try:
        price = get_ticker_price(symbol)
        klines = fetch_klines(symbol, interval=timeframe, limit=200)
        closes = get_closes_from_klines(klines)
        if not closes:
            return {"symbol": symbol, "error": "no historical closes available"}

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
        order_type = "LIMIT"  # Default to limit orders
        
        # Dynamic TP/SL based on volatility and confidence
        base_tp_pct = 0.015 + (confidence * 0.005)  # 1.5% to 3%
        base_sl_pct = 0.008 + (confidence * 0.002)  # 0.8% to 1.4%
        
        if final == "BUY":
            tp_long = round(price * (1 + base_tp_pct), 6)
            sl_long = round(price * (1 - base_sl_pct), 6)
            # Use market order for strong signals
            order_type = "MARKET" if confidence >= 3 else "LIMIT"
        elif final == "SELL":
            tp_short = round(price * (1 - base_tp_pct), 6)
            sl_short = round(price * (1 + base_sl_pct), 6)
            # Use market order for strong signals  
            order_type = "MARKET" if confidence >= 3 else "LIMIT"

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
            "timestamp": datetime.now().strftime("%H:%M:%S")
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
            
            message += f"\n🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`"
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
    """Send a consolidated message with all signals to Telegram"""
    if not signals:
        return
        
    # Separate signals by type
    buy_signals = [s for s in signals if s.get("signal") == "BUY" and not s.get("error")]
    sell_signals = [s for s in signals if s.get("signal") == "SELL" and not s.get("error")]
    hold_signals = [s for s in signals if s.get("signal") == "HOLD" and not s.get("error")]
    errors = [s for s in signals if s.get("error")]
    
    message = f"📊 *15-Minute Crypto Signals Update*\n"
    message += f"🕐 Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
    
    if buy_signals:
        message += f"🟢 *BUY SIGNALS ({len(buy_signals)}):*\n"
        for signal in buy_signals:
            confidence_stars = "⭐" * min(int(signal.get('confidence', 0)), 3)
            order_type = signal.get('order_type', 'LIMIT')
            message += f"• `{signal['symbol']}` @ ${signal['price']:,.2f} {confidence_stars}\n"
            message += f"  {order_type} | RSI: {signal['rsi']:.1f} | TP: ${signal.get('take_profit_long', 0):,.2f}\n"
        message += "\n"
    
    if sell_signals:
        message += f"🔴 *SELL SIGNALS ({len(sell_signals)}):*\n"
        for signal in sell_signals:
            confidence_stars = "⭐" * min(int(signal.get('confidence', 0)), 3)
            order_type = signal.get('order_type', 'LIMIT')
            message += f"• `{signal['symbol']}` @ ${signal['price']:,.2f} {confidence_stars}\n"
            message += f"  {order_type} | RSI: {signal['rsi']:.1f} | TP: ${signal.get('take_profit_short', 0):,.2f}\n"
        message += "\n"
    
    if hold_signals:
        message += f"🟡 *HOLD ({len(hold_signals)} pairs):*\n"
        # Show first 5 HOLD signals to avoid message being too long
        for signal in hold_signals[:5]:
            message += f"• `{signal['symbol']}` @ ${signal['price']:,.2f}\n"
        if len(hold_signals) > 5:
            message += f"• ... and {len(hold_signals) - 5} more\n"
        message += "\n"
    
    if errors:
        message += f"❌ *Errors ({len(errors)}):* {', '.join(s['symbol'] for s in errors)}\n"
    
    message += f"\n_Next update in 15 minutes ⏰_"
    
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
    stop_auto_signals()
    await update.message.reply_text("🛑 Auto signals stopped!")

async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command from Telegram bot"""
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
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ No Telegram bot token provided")
        return None
        
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
    Each candle is [time, open, close, high, low, volume] (KuCoin order can vary)
    We attempt to access close at index 2, fallback checks included.
    """
    closes = []
    for c in klines:
        try:
            close = float(c[2])
        except Exception:
            # try last element
            close = float(c[-1])
        closes.append(close)
    return closes

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    # initial avg
    for i in range(1, period + 1):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    # Wilder smoothing for remaining values
    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i-1]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
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

def generate_signal(symbol: str = "BTC-USDT", timeframe: str = "1hour"):
    """
    Enhanced trading signal generation with improved technical analysis.
    Used by the API endpoint - calls the enhanced generate_single_signal function.
    """
    return generate_single_signal(symbol, timeframe, send_notification=True)