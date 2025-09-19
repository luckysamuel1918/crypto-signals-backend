from backend.signals import generate_signal

def simple_strategy(symbol: str = "BTC-USDT", timeframe: str = "1hour"):
    """
    Small wrapper that returns generate_signal output.
    Keep for future expansion.
    """
    return generate_signal(symbol, timeframe)
