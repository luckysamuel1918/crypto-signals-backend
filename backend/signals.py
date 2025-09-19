import os
import requests
from typing import List, Optional
from backend.kucoin_service import get_ticker_price, fetch_klines

# 🔐 Get Telegram credentials from environment variables (secure)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message: str):
    """Send a notification to your Telegram bot"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        print("✅ Telegram notification sent")
    except requests.exceptions.HTTPError as e:
        if "chat not found" in str(e).lower():
            print("❌ Telegram error: Chat not found. Please send /start to your bot first!")
        else:
            print(f"❌ Telegram HTTP error: {e}")
    except Exception as e:
        print("❌ Telegram send failed:", e)

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
    Generate a trading signal with advanced technical analysis and send to Telegram.
    Returns a dict with:
    - symbol, price, signal (BUY/SELL/HOLD), rsi, ema12, ema26, take_profit, stop_loss
    Strategy:
      - RSI-based primary signal:
          RSI < 30 => BUY
          RSI > 70 => SELL
      - EMA12/EMA26 used as confirmation:
          if EMA12 > EMA26 -> bullish
          if EMA12 < EMA26 -> bearish
      - TP/SL fixed % (tweakable)
    """
    # fetch current price (fast) and klines (for indicators)
    price = get_ticker_price(symbol)
    klines = fetch_klines(symbol, interval=timeframe, limit=200)
    closes = get_closes_from_klines(klines)
    if not closes:
        return {"error": "no historical closes available"}

    rsi = calculate_rsi(closes, period=14)
    ema12 = simple_ema(closes, 12)
    ema26 = simple_ema(closes, 26)

    # Decide
    signal = "HOLD"
    if rsi is not None:
        if rsi < 30:
            signal = "BUY"
        elif rsi > 70:
            signal = "SELL"
    # Confirmation with EMAs
    if ema12 is not None and ema26 is not None:
        if ema12 > ema26 and signal == "BUY":
            final = "BUY"
        elif ema12 < ema26 and signal == "SELL":
            final = "SELL"
        else:
            final = "HOLD"
    else:
        final = signal

    tp = None
    sl = None
    TP_PCT = 0.02  # 2%
    SL_PCT = 0.01  # 1%
    if final == "BUY":
        tp = round(price * (1 + TP_PCT), 6)
        sl = round(price * (1 - SL_PCT), 6)
    elif final == "SELL":
        tp = round(price * (1 - TP_PCT), 6)
        sl = round(price * (1 + SL_PCT), 6)

    # 🚨 Send Telegram notification for all signals
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
    message = (
        f"🚨 *Crypto Signal Alert*\n"
        f"Pair: `{symbol}`\n"
        f"Price: `${price:,.2f}`\n"
        f"Signal: {emoji.get(final, '⚪')} *{final}*\n"
        f"RSI: `{rsi}` | EMA12: `{ema12:.2f}` | EMA26: `{ema26:.2f}`"
    )
    
    if tp and sl:
        message += f"\nTake Profit: `${tp:,.2f}`\nStop Loss: `${sl:,.2f}`"
    
    send_telegram_message(message)

    return {
        "symbol": symbol,
        "price": round(price, 6),
        "signal": final,
        "rsi": rsi,
        "ema12": round(ema12, 6) if ema12 else None,
        "ema26": round(ema26, 6) if ema26 else None,
        "take_profit": tp,
        "stop_loss": sl
    }