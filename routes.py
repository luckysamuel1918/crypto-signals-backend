from fastapi import APIRouter, HTTPException, Query
from backend.signals import generate_signal

router = APIRouter()

@router.get("/signal")
def get_signal(symbol: str = Query("BTC-USDT", description="Symbol like BTC-USDT"), timeframe: str = Query("1hour", description="Candle timeframe")):
    """
    Example: GET /api/signal?symbol=BTC-USDT&timeframe=1hour
    """
    try:
        return generate_signal(symbol.upper(), timeframe)
    except Exception as e:
        # return a helpful message for debugging
        raise HTTPException(status_code=500, detail=str(e))
