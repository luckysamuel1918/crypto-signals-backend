from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import router as routes_router
from backend.signals import setup_telegram_bot, generate_scheduled_signals
from backend.websocket_manager import WebSocketPriceManager
from backend.realtime_signal_engine import RealtimeSignalEngine
from backend.execution_manager import ExecutionManager
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import os

app = FastAPI(title="Lucky Signals Backend - Real-Time Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(routes_router, prefix="/api", tags=["signals"])

# Global variables
scheduler = None
ws_manager = None
signal_engine = None
execution_manager = None

@app.on_event("startup")
async def startup_event():
    """Initialize real-time trading system on FastAPI startup"""
    global scheduler, ws_manager, signal_engine, execution_manager
    
    print("\n" + "="*60)
    print("🚀 STARTING REAL-TIME TRADING SYSTEM")
    print("="*60 + "\n")
    
    # Setup Telegram messaging (direct API calls, no bot polling)
    setup_telegram_bot()
    
    # Initialize WebSocket Price Manager
    print("📡 Initializing WebSocket Price Manager...")
    ws_manager = WebSocketPriceManager()
    await ws_manager.start()
    
    # Initialize Real-Time Signal Engine
    print("🎯 Initializing Real-Time Signal Engine...")
    signal_engine = RealtimeSignalEngine(ws_manager)
    
    # Initialize Execution Manager
    print("⚡ Initializing Execution Manager...")
    execution_manager = ExecutionManager()
    
    # Start monitoring top crypto pairs
    print("\n📊 Starting real-time monitoring for top pairs...")
    top_pairs = ["BTC-USDT", "ETH-USDT", "BNB-USDT"]
    
    for symbol in top_pairs:
        await signal_engine.start_monitoring(symbol, "1hour")
        await asyncio.sleep(0.5)  # Small delay between subscriptions
    
    # Start APScheduler for periodic indicator updates (backup)
    print("\n⏰ Starting backup scheduler...")
    scheduler = BackgroundScheduler()
    
    # Schedule signal generation every 15 minutes as backup
    scheduler.add_job(
        generate_scheduled_signals,
        'interval',
        minutes=15,
        id='signal_generation_backup',
        name='Backup signal generation every 15 minutes',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Backup scheduler started")
    
    print("\n" + "="*60)
    print("✅ REAL-TIME TRADING SYSTEM RUNNING")
    print("="*60)
    print("📊 Monitoring: " + ", ".join(top_pairs))
    print("🔌 WebSocket: Active with REST API fallback")
    print("⚡ Execution: Instant with ±0.2% price tolerance")
    print("⏱️ Delay Check: Skip if > 2 seconds")
    print("="*60 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of all systems"""
    global scheduler, ws_manager
    
    print("\n🛑 Shutting down Real-Time Trading System...")
    
    # Shutdown WebSocket
    if ws_manager:
        await ws_manager.stop()
        print("✅ WebSocket Manager stopped")
    
    # Shutdown scheduler
    if scheduler:
        scheduler.shutdown()
        print("✅ Scheduler stopped")
        
    print("✅ Shutdown complete\n")

@app.get("/")
def root():
    return {
        "message": "Lucky Signals Backend - Real-Time Trading Signals API",
        "version": "3.0.0 - Real-Time Edition",
        "endpoints": {
            "/api/signal": "Get trading signal for a symbol",
            "/docs": "API documentation"
        },
        "features": {
            "websocket": "Real-time price streaming from KuCoin",
            "execution": "Instant order execution with ±0.2% price tolerance",
            "delay_check": "Skip signals if delay > 2 seconds",
            "fallback": "Automatic REST API fallback if WebSocket fails",
            "async_processing": "Parallel processing for faster signal generation"
        },
        "monitored_pairs": ["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        "disclaimer": "⚠️ RISK WARNING: Trading cryptocurrencies involves substantial risk of loss. Signals are for educational purposes only. Always do your own research and never invest more than you can afford to lose.",
        "data_source": "KuCoin API (WebSocket + REST)",
        "indicators": ["RSI-14", "EMA-12", "EMA-26"]
    }
