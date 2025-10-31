from fastapi import APIRouter, HTTPException, Query, Body
from backend.signals import generate_signal
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# Global references (set by app.py)
_signal_engine = None
_trade_executor = None

def set_signal_engine(engine):
    """Set the global signal engine reference"""
    global _signal_engine
    _signal_engine = engine

def set_trade_executor(executor):
    """Set the global trade executor reference"""
    global _trade_executor
    _trade_executor = executor

class TradingSettings(BaseModel):
    """Trading configuration settings"""
    auto_execute: bool
    order_size_usdt: Optional[float] = None

@router.get("/signal")
def get_signal(
    symbol: str = Query("BTC-USDT", description="Symbol like BTC-USDT"),
    timeframe: str = Query("1hour", description="Candle timeframe"),
    execute: bool = Query(False, description="Execute trade automatically if auto-trading enabled")
):
    """
    Get trading signal and optionally execute trade
    
    Args:
        symbol: Trading pair (e.g., BTC-USDT)
        timeframe: Candle timeframe
        execute: If True and auto-trading enabled, execute the trade
    
    Example: GET /api/signal?symbol=BTC-USDT&timeframe=1hour&execute=true
    """
    try:
        # Manual request from user - always send Telegram notification
        signal_data = generate_signal(symbol.upper(), timeframe, manual_request=True)
        
        # Execute trade if requested and trade executor is available
        if execute and _trade_executor:
            execution_result = _trade_executor.execute_signal(signal_data, force=False)
            signal_data["execution"] = execution_result
        
        return signal_data
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

@router.get("/trading/status")
def get_trading_status():
    """
    Get trading automation status
    
    Returns:
        Auto-execution status and configuration
    """
    if not _trade_executor:
        return {
            "status": "not_configured",
            "auto_execute": False,
            "message": "Trade executor not initialized"
        }
    
    kucoin_configured = _trade_executor.kucoin_client and _trade_executor.kucoin_client.is_configured()
    mode = _trade_executor.kucoin_client.mode if kucoin_configured else "unknown"
    
    return {
        "status": "configured" if kucoin_configured else "not_configured",
        "auto_execute": _trade_executor.auto_execute,
        "order_size_usdt": _trade_executor.order_size_usdt,
        "mode": mode,
        "kucoin_configured": kucoin_configured
    }

@router.post("/trading/settings")
def update_trading_settings(settings: TradingSettings):
    """
    Update trading automation settings
    
    Args:
        settings: Trading configuration (auto_execute, order_size_usdt)
    
    Returns:
        Updated settings confirmation
    """
    if not _trade_executor:
        raise HTTPException(status_code=503, detail="Trade executor not initialized")
    
    try:
        _trade_executor.set_auto_execute(settings.auto_execute)
        
        if settings.order_size_usdt is not None:
            _trade_executor.set_order_size(settings.order_size_usdt)
        
        return {
            "status": "success",
            "auto_execute": _trade_executor.auto_execute,
            "order_size_usdt": _trade_executor.order_size_usdt,
            "message": "Trading settings updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading/execute")
def execute_trade(signal_data: dict = Body(...)):
    """
    Manually execute a trade based on signal data
    
    Args:
        signal_data: Signal dictionary with entry, take_profit, stop_loss
    
    Returns:
        Execution result
    """
    if not _trade_executor:
        raise HTTPException(status_code=503, detail="Trade executor not initialized")
    
    try:
        result = _trade_executor.execute_signal(signal_data, force=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trading/history")
def get_execution_history(limit: int = Query(10, description="Number of recent executions", ge=1, le=100)):
    """
    Get recent trade execution history
    
    Args:
        limit: Maximum number of executions to return
    
    Returns:
        List of recent trade executions
    """
    if not _trade_executor:
        raise HTTPException(status_code=503, detail="Trade executor not initialized")
    
    try:
        history = _trade_executor.get_execution_history(limit)
        return {
            "status": "success",
            "count": len(history),
            "executions": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
