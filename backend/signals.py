import requests
import os
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from backend.kucoin_service import get_ticker_price, fetch_klines

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 🎯 Top cryptocurrency pairs for signal generation
CRYPTO_PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "XRP-USDT", "ADA-USDT",
    "DOGE-USDT", "SOL-USDT", "MATIC-USDT", "DOT-USDT", "AVAX-USDT",
    "UNI-USDT", "LINK-USDT", "LTC-USDT", "ATOM-USDT", "BCH-USDT",
    "NEAR-USDT", "FTT-USDT", "ALGO-USDT", "XLM-USDT", "ICP-USDT"
]

def send_telegram_message(text: str):
    """Send message to Telegram"""
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured - skipping message")
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

def _split_telegram_message(text: str, max_length: int) -> List[str]:
    """Split a long message into smaller chunks while preserving formatting"""
    chunks = []
    lines = text.split('\n')
    current_chunk = ""
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        current_chunk += line + "\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def get_ohlcv_data(symbol: str, timeframe: str, limit: int = 100) -> List[Dict]:
    """
    Fetch OHLCV (candlestick) data from KuCoin API
    Returns list of candles with OHLCV data
    """
    try:
        klines = fetch_klines(symbol, interval=timeframe, limit=limit)
        if not klines:
            return []
        
        ohlcv_data = []
        for candle in klines:
            # KuCoin structure: [timestamp, open, close, high, low, volume, turnover]
            ohlcv_data.append({
                'timestamp': float(candle[0]),
                'open': float(candle[1]),
                'close': float(candle[2]),
                'high': float(candle[3]),
                'low': float(candle[4]),
                'volume': float(candle[5])
            })
        
        return ohlcv_data
    except Exception as e:
        print(f"❌ Error fetching OHLCV data for {symbol}: {e}")
        return []

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return []
    
    # Initialize with SMA for first value
    sma = sum(prices[:period]) / period
    ema_values = [sma]
    
    # Calculate multiplier
    multiplier = 2 / (period + 1)
    
    # Calculate EMA for remaining values
    for i in range(period, len(prices)):
        ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
        ema_values.append(ema)
    
    return ema_values

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI using Wilder's smoothing method"""
    if len(prices) < period + 1:
        return None
    
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
    
    # Initial average gain and loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Apply Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)

def calculate_atr(ohlcv_data: List[Dict], period: int = 14) -> Optional[float]:
    """Calculate Average True Range for volatility measurement"""
    if len(ohlcv_data) < period + 1:
        return None
    
    true_ranges = []
    
    for i in range(1, len(ohlcv_data)):
        current = ohlcv_data[i]
        previous = ohlcv_data[i-1]
        
        high_low = current['high'] - current['low']
        high_close_prev = abs(current['high'] - previous['close'])
        low_close_prev = abs(current['low'] - previous['close'])
        
        true_range = max(high_low, high_close_prev, low_close_prev)
        true_ranges.append(true_range)
    
    if len(true_ranges) < period:
        return None
    
    # Calculate ATR using simple moving average of true ranges
    atr = sum(true_ranges[-period:]) / period
    return round(atr, 6)

def analyze_timeframe(symbol: str, timeframe: str) -> Dict:
    """Analyze a single timeframe and return indicators"""
    try:
        ohlcv_data = get_ohlcv_data(symbol, timeframe, limit=100)
        if not ohlcv_data or len(ohlcv_data) < 50:
            return {"error": f"Insufficient data for {timeframe}"}
        
        # Extract close prices
        closes = [candle['close'] for candle in ohlcv_data]
        current_price = closes[-1]
        
        # Calculate EMAs
        ema12_values = calculate_ema(closes, 12)
        ema26_values = calculate_ema(closes, 26)
        
        if not ema12_values or not ema26_values:
            return {"error": f"Insufficient data for EMA calculation in {timeframe}"}
        
        ema12 = ema12_values[-1]
        ema26 = ema26_values[-1]
        
        # Calculate RSI
        rsi = calculate_rsi(closes, 14)
        
        # Calculate ATR
        atr = calculate_atr(ohlcv_data, 14)
        
        # Determine trend
        trend = "BULLISH" if ema12 > ema26 else "BEARISH"
        
        return {
            "timeframe": timeframe,
            "current_price": current_price,
            "ema12": round(ema12, 6),
            "ema26": round(ema26, 6),
            "rsi": rsi,
            "atr": atr,
            "trend": trend,
            "price_vs_ema12": "ABOVE" if current_price > ema12 else "BELOW"
        }
        
    except Exception as e:
        return {"error": f"Analysis error for {timeframe}: {str(e)}"}

def generate_signal(symbol: str = "BTC-USDT", timeframe: str = "1hour") -> Dict:
    """
    Generate realistic crypto trading signals with multi-timeframe analysis
    Targets 70-80% accuracy with strict technical analysis rules
    """
    try:
        print(f"🔍 Analyzing {symbol} across multiple timeframes...")
        
        # Analyze multiple timeframes
        timeframes = ["15min", "1hour", "4hour"]
        analyses = {}
        
        for tf in timeframes:
            analyses[tf] = analyze_timeframe(symbol, tf)
            if "error" in analyses[tf]:
                print(f"⚠️ {analyses[tf]['error']}")
        
        # Filter out failed analyses
        valid_analyses = {tf: data for tf, data in analyses.items() if "error" not in data}
        
        if len(valid_analyses) < 2:
            return {
                "symbol": symbol,
                "signal": "HOLD",
                "reason": "Insufficient data across timeframes",
                "error": "Need at least 2 valid timeframes for analysis"
            }
        
        # Fetch real-time current price from KuCoin API
        try:
            current_price = get_ticker_price(symbol)
            print(f"💰 Real-time price from KuCoin API: ${current_price:,.2f}")
        except Exception as e:
            print(f"⚠️ Failed to fetch real-time price, using OHLCV data: {e}")
            # Fallback to price from OHLCV data if API call fails
            primary_tf = "1hour" if "1hour" in valid_analyses else list(valid_analyses.keys())[0]
            current_price = valid_analyses[primary_tf]["current_price"]
        
        # Use the primary timeframe for indicators
        primary_tf = "1hour" if "1hour" in valid_analyses else list(valid_analyses.keys())[0]
        primary_data = valid_analyses[primary_tf]
        
        ema12 = primary_data["ema12"]
        ema26 = primary_data["ema26"]
        rsi = primary_data["rsi"]
        atr = primary_data["atr"]
        
        # Debug logging for indicators
        print(f"📊 Technical Indicators:")
        print(f"   RSI: {rsi:.2f}")
        print(f"   EMA12: ${ema12:,.2f}")
        print(f"   EMA26: ${ema26:,.2f}")
        print(f"   ATR: ${atr:,.2f}")
        
        # Count bullish and bearish timeframes
        bullish_count = sum(1 for data in valid_analyses.values() if data["trend"] == "BULLISH")
        bearish_count = sum(1 for data in valid_analyses.values() if data["trend"] == "BEARISH")
        
        # Calculate confidence based on timeframe agreement
        total_timeframes = len(valid_analyses)
        confidence = max(bullish_count, bearish_count) / total_timeframes
        
        # Simplified signal logic - BUY if RSI < 50 and EMA12 > EMA26, SELL if RSI > 50 and EMA12 < EMA26
        signal = "HOLD"
        signal_reasons = []
        entry_price = current_price
        
        # BUY Signal: RSI < 50 and EMA12 > EMA26
        if rsi is not None and rsi < 50 and ema12 > ema26:
            signal = "BUY"
            entry_price = current_price
            signal_reasons.append(f"RSI below 50 ({rsi:.1f} < 50)")
            signal_reasons.append(f"Bullish EMA trend (EMA12 {ema12:,.2f} > EMA26 {ema26:,.2f})")
            signal_reasons.append(f"{bullish_count}/{total_timeframes} timeframes confirm bullish trend")
            print(f"✅ BUY Signal Generated: RSI={rsi:.1f}, EMA12={ema12:,.2f}, EMA26={ema26:,.2f}")
        
        # SELL Signal: RSI > 50 and EMA12 < EMA26
        elif rsi is not None and rsi > 50 and ema12 < ema26:
            signal = "SELL"
            entry_price = current_price
            signal_reasons.append(f"RSI above 50 ({rsi:.1f} > 50)")
            signal_reasons.append(f"Bearish EMA trend (EMA12 {ema12:,.2f} < EMA26 {ema26:,.2f})")
            signal_reasons.append(f"{bearish_count}/{total_timeframes} timeframes confirm bearish trend")
            print(f"✅ SELL Signal Generated: RSI={rsi:.1f}, EMA12={ema12:,.2f}, EMA26={ema26:,.2f}")
        
        # HOLD: Both conditions fail
        else:
            signal = "HOLD"
            if rsi is not None:
                signal_reasons.append(f"RSI: {rsi:.1f} (BUY if < 50, SELL if > 50)")
            signal_reasons.append(f"EMA12: ${ema12:,.2f}, EMA26: ${ema26:,.2f} (BUY if EMA12 > EMA26, SELL if EMA12 < EMA26)")
            signal_reasons.append("Conditions not met for BUY or SELL")
            print(f"⏸️ HOLD Signal: RSI={rsi:.1f}, EMA12={ema12:,.2f}, EMA26={ema26:,.2f}")
        
        # Calculate Risk Management levels with fixed percentages
        # For BUY: Take Profit +1.5%, Stop Loss -1%
        # For SELL: Take Profit -1.5%, Stop Loss +1%
        take_profit = None
        stop_loss = None
        
        if signal == "BUY":
            take_profit = round(entry_price * 1.015, 6)  # +1.5%
            stop_loss = round(entry_price * 0.99, 6)  # -1%
        elif signal == "SELL":
            take_profit = round(entry_price * 0.985, 6)  # -1.5%
            stop_loss = round(entry_price * 1.01, 6)  # +1%
        
        # Only send signals with confidence >= 0.70 (at least 2/3 timeframes agree)
        should_send_telegram = confidence >= 0.70
        
        # Prepare result
        result = {
            "symbol": symbol,
            "signal": signal,
            "current_price": round(current_price, 6),
            "entry_price": round(entry_price, 6),
            "ema12": ema12,
            "ema26": ema26,
            "rsi": rsi,
            "atr": atr,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "confidence": round(confidence, 2),
            "timeframe_analysis": {
                "bullish_timeframes": bullish_count,
                "bearish_timeframes": bearish_count,
                "total_timeframes": total_timeframes
            },
            "reasons": signal_reasons,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timeframes_analyzed": list(valid_analyses.keys()),
            "should_send_telegram": should_send_telegram
        }
        
        # Send Telegram notification
        send_signal_to_telegram(result)
        
        return result
        
    except Exception as e:
        error_result = {
            "symbol": symbol,
            "signal": "HOLD",
            "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        send_signal_to_telegram(error_result)
        return error_result

def send_signal_to_telegram(signal_data: Dict):
    """Send formatted signal to Telegram with rich details - only if confidence >= 0.70"""
    try:
        # Only send if confidence >= 0.70 (or if there's an error to report)
        should_send = signal_data.get("should_send_telegram", False) or "error" in signal_data
        confidence = signal_data.get("confidence", 0)
        
        if not should_send and confidence < 0.70:
            print(f"⏭️ Skipping Telegram notification (confidence {confidence:.2f} < 0.70)")
            return
        
        symbol = signal_data.get("symbol", "N/A")
        signal = signal_data.get("signal", "HOLD")
        entry_price = signal_data.get("entry_price", signal_data.get("current_price", 0))
        ema12 = signal_data.get("ema12", 0)
        ema26 = signal_data.get("ema26", 0)
        rsi = signal_data.get("rsi", 0)
        take_profit = signal_data.get("take_profit")
        stop_loss = signal_data.get("stop_loss")
        timestamp = signal_data.get("timestamp", "")
        reasons = signal_data.get("reasons", [])
        timeframe_analysis = signal_data.get("timeframe_analysis", {})
        
        # Signal emoji
        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴", 
            "HOLD": "🟡"
        }.get(signal, "⚪")
        
        # Format message according to user specifications
        message = f"🚨 Crypto Signal Alert\n"
        message += f"Pair: {symbol}\n"
        message += f"Signal: {signal_emoji} {signal}\n"
        message += f"Entry: ${entry_price:,.2f}\n"
        
        # Calculate and display percentage changes
        if take_profit and stop_loss:
            if signal == "BUY":
                tp_pct = ((take_profit - entry_price) / entry_price) * 100
                sl_pct = ((stop_loss - entry_price) / entry_price) * 100
                message += f"Take Profit: ${take_profit:,.2f} (+{tp_pct:.1f}%)\n"
                message += f"Stop Loss: ${stop_loss:,.2f} ({sl_pct:.1f}%)\n"
            elif signal == "SELL":
                tp_pct = ((entry_price - take_profit) / entry_price) * 100
                sl_pct = ((stop_loss - entry_price) / entry_price) * 100
                message += f"Take Profit: ${take_profit:,.2f} (−{tp_pct:.1f}%)\n"
                message += f"Stop Loss: ${stop_loss:,.2f} (+{sl_pct:.1f}%)\n"
        else:
            message += f"Take Profit: N/A\n"
            message += f"Stop Loss: N/A\n"
        
        if rsi is not None and ema12 is not None and ema26 is not None:
            message += f"RSI: {rsi:.1f} | EMA12: {ema12:,.2f} | EMA26: {ema26:,.2f}\n"
        
        # Show confidence based on timeframe agreement
        matched_timeframes = max(timeframe_analysis.get('bullish_timeframes', 0), 
                                timeframe_analysis.get('bearish_timeframes', 0))
        total_timeframes = timeframe_analysis.get('total_timeframes', 3)
        message += f"Confidence: {matched_timeframes}/{total_timeframes} timeframes matched\n"
        message += f"Time: {timestamp}"
        
        send_telegram_message(message)
        
    except Exception as e:
        error_msg = f"❌ *Signal Generation Error*\n"
        error_msg += f"Symbol: `{signal_data.get('symbol', 'Unknown')}`\n"
        error_msg += f"Error: `{str(e)}`\n"
        error_msg += f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        send_telegram_message(error_msg)

def generate_scheduled_signals():
    """Generate signals for top crypto pairs - called by scheduler"""
    print("📊 Generating scheduled signals...")
    
    # Generate signals for top pairs (limit to avoid rate limiting)
    top_pairs = ["BTC-USDT", "ETH-USDT", "BNB-USDT"]
    
    for symbol in top_pairs:
        try:
            print(f"   Analyzing {symbol}...")
            generate_signal(symbol, "1hour")
            # Small delay to avoid overwhelming the API
            import time
            time.sleep(2)
        except Exception as e:
            print(f"   ❌ Error analyzing {symbol}: {e}")
    
    print("✅ Scheduled signal generation complete")

# Compatibility functions for existing API
def generate_single_signal(symbol: str, timeframe: str = "1hour", send_notification: bool = True) -> Dict:
    """Generate signal with notification control"""
    result = generate_signal(symbol, timeframe)
    return result

def generate_signal_with_notification(symbol: str = "BTC-USDT", timeframe: str = "1hour"):
    """Generate signal for backward compatibility with existing API"""
    return generate_signal(symbol, timeframe)

def setup_telegram_bot():
    """Setup Telegram bot - compatibility function for app.py"""
    # In the new implementation, we send messages directly without bot polling
    # This function is kept for compatibility with app.py
    print("✅ Telegram messaging enabled (direct API calls)")
    return None