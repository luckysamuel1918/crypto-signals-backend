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
    KuCoin returns arrays: [time, open, close, high, low, volume]
    """
    symbol_param = symbol.replace("/", "-").upper()
    url = f"{KUCOIN_API_BASE}/api/v1/market/candles?type={interval}&symbol={symbol_param}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    js = resp.json()
    data = js.get("data") or []
    # KuCoin returns newest->oldest typically; reverse it to oldest->newest
    candles = list(reversed(data))
    return candles[:limit]
