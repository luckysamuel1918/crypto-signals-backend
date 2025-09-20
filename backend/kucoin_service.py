import os
import requests
from dotenv import load_dotenv

load_dotenv()

KUCOIN_API_BASE = "https://api.kucoin.com"

def get_ticker_price(symbol: str = "BTC-USDT") -> float:
    """
    Public level1 ticker from KuCoin.
    Returns price as float, or raises on error.
    """
    symbol_param = symbol.replace("/", "-").upper()
    url = f"{KUCOIN_API_BASE}/api/v1/market/orderbook/level1?symbol={symbol_param}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # data["data"]["price"] is usually the key
    price = data.get("data", {}).get("price")
    if price is None:
        raise RuntimeError(f"No price in KuCoin response: {data}")
    return float(price)

def fetch_klines(symbol: str = "BTC-USDT", interval: str = "1hour", limit: int = 200):
    """
    Fetch KuCoin candles. Returns list of candles (oldest -> newest).
    KuCoin returns arrays: [timestamp, open, close, high, low, volume, turnover]
    Verified structure: Index 2 = close price
    EXCLUDES the latest incomplete candle to prevent repainting.
    """
    symbol_param = symbol.replace("/", "-").upper()
    url = f"{KUCOIN_API_BASE}/api/v1/market/candles?type={interval}&symbol={symbol_param}"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        js = resp.json()
        
        # Validate API response structure
        if js.get("code") != "200000":
            raise RuntimeError(f"KuCoin API error: {js.get('msg', 'Unknown error')}")
            
        data = js.get("data") or []
        if not data:
            raise RuntimeError(f"No candle data returned for {symbol}")
            
        # Validate each candle has proper structure
        for i, candle in enumerate(data):
            if len(candle) < 7:
                raise RuntimeError(f"Invalid candle structure at index {i}: {candle}")
        
        # KuCoin returns newest->oldest; reverse to oldest->newest for proper TA calculation
        candles = list(reversed(data))
        
        # CRITICAL: Remove the latest candle to prevent repainting (incomplete candle)
        # The most recent candle is still forming and will change, causing signal repainting
        if len(candles) > 1:
            candles = candles[:-1]  # Remove the most recent incomplete candle
            
        return candles[:limit]
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch candle data: {e}")
    except Exception as e:
        raise RuntimeError(f"Error processing candle data: {e}")
