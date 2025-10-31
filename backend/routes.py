from fastapi import APIRouter, HTTPException, Query
from backend.signals import generate_signal
from typing import Optional

router = APIRouter()

# Global reference to signal engine (set by app.py)
_signal_engine = None

def set_signal_engine(engine):
    """Set the global signal engine reference"""
    global _signal_engine
    _signal_engine = engine

@router.get("/signal")
def get_signal(symbol: str = Query("BTC-USDT", description="Symbol like BTC-USDT"), timeframe: str = Query("1hour", description="Candle timeframe")):
    """
    Example: GET /api/signal?symbol=BTC-USDT&timeframe=1hour
    """
    try:
        # Manual request from user - always send Telegram notification
        return generate_signal(symbol.upper(), timeframe, manual_request=True)
    except Exception as e:
        # return a helpful message for debugging
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/predictions")
def get_prediction_stats():
    """
    Get pre-signal prediction accuracy statistics
    
    Returns:
        Statistics on how accurate the pre-signal predictions have been
    """
    if not _signal_engine:
        raise HTTPException(status_code=503, detail="Signal engine not initialized")
    
    try:
        stats = _signal_engine.get_prediction_stats()
        return {
            "status": "success",
            "data": stats,
            "description": "Pre-signal prediction accuracy statistics"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings/lead-time")
def get_lead_time():
    """
    Get current signal lead time configuration
    
    Returns:
        Current lead time in seconds for pre-signal alerts
    """
    if not _signal_engine:
        raise HTTPException(status_code=503, detail="Signal engine not initialized")
    
    return {
        "status": "success",
        "lead_time_seconds": _signal_engine.signal_lead_time,
        "description": "Time in seconds before signal triggers to send pre-signal alert"
    }

@router.post("/settings/lead-time")
def update_lead_time(seconds: int = Query(..., description="Lead time in seconds (20-60)", ge=20, le=60)):
    """
    Update signal lead time for pre-signal alerts
    
    Args:
        seconds: Lead time in seconds (20-60 seconds)
        
    Returns:
        Confirmation of updated lead time
    """
    if not _signal_engine:
        raise HTTPException(status_code=503, detail="Signal engine not initialized")
    
    try:
        _signal_engine.set_signal_lead_time(seconds)
        return {
            "status": "success",
            "lead_time_seconds": seconds,
            "message": f"Signal lead time updated to {seconds} seconds"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-signals")
def get_active_signals():
    """
    Get currently active signals
    
    Returns:
        Dictionary of active signals by symbol
    """
    if not _signal_engine:
        raise HTTPException(status_code=503, detail="Signal engine not initialized")
    
    try:
        active = _signal_engine.get_active_signals()
        return {
            "status": "success",
            "active_signals": active,
            "count": len(active)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
