from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import router as routes_router, set_signal_engine, set_trade_executor
from backend.signals import setup_telegram_bot, generate_scheduled_signals
from backend.websocket_manager import WebSocketPriceManager
from backend.realtime_signal_engine import RealtimeSignalEngine
from backend.execution_manager import ExecutionManager
from backend.kucoin_client import KuCoinClient
from backend.trade_executor import TradeExecutor
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
kucoin_client = None
trade_executor = None

@app.on_event("startup")
async def startup_event():
    """Initialize real-time trading system on FastAPI startup"""
    global scheduler, ws_manager, signal_engine, execution_manager, kucoin_client, trade_executor
    
    print("\n" + "="*60)
    print("🚀 STARTING REAL-TIME TRADING SYSTEM")
    print("="*60 + "\n")
    
    # Setup Telegram messaging (direct API calls, no bot polling)
    setup_telegram_bot()
    
    # Initialize KuCoin Client for automated trading
    print("💼 Initializing KuCoin Trading Client...")
    trading_mode = os.getenv("KUCOIN_MODE", "sandbox")  # sandbox or live
    kucoin_client = KuCoinClient(mode=trading_mode)
    
    # Initialize Trade Executor
    print("⚡ Initializing Trade Executor...")
    auto_execute = os.getenv("AUTO_EXECUTE", "false").lower() == "true"
    order_size_usdt = float(os.getenv("ORDER_SIZE_USDT", "10.0"))
    trade_executor = TradeExecutor(
        kucoin_client=kucoin_client,
        auto_execute=auto_execute,
        order_size_usdt=order_size_usdt
    )
    
    # Initialize WebSocket Price Manager
    print("📡 Initializing WebSocket Price Manager...")
    ws_manager = WebSocketPriceManager()
    await ws_manager.start()
    
    # Initialize Execution Manager
    print("⚡ Initializing Execution Manager...")
    execution_manager = ExecutionManager()
    
    # Initialize Real-Time Signal Engine (with execution manager)
    print("🎯 Initializing Real-Time Signal Engine...")
    
    # Get signal lead time from environment (default 30 seconds)
    signal_lead_time = int(os.getenv("SIGNAL_LEAD_TIME", "30"))
    print(f"⚡ Pre-signal lead time: {signal_lead_time} seconds")
    
    signal_engine = RealtimeSignalEngine(ws_manager, execution_manager, signal_lead_time=signal_lead_time)
    
    # Set references for API routes
    set_signal_engine(signal_engine)
    set_trade_executor(trade_executor)
    
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
    print(f"🔮 Pre-Signal Alerts: {signal_lead_time}s lead time (≥90% confidence)")
    print(f"🤖 Auto-Trading: {'ENABLED' if auto_execute else 'DISABLED'} ({trading_mode} mode)")
    print(f"💵 Order Size: ${order_size_usdt} USDT")
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
    # Get current lead time if signal engine is initialized
    lead_time = signal_engine.signal_lead_time if signal_engine else 30
    
    return {
        "message": "Lucky Signals Backend - Real-Time Trading Signals API",
        "version": "4.0.0 - Pre-Signal Alerts Edition",
        "endpoints": {
            "/api/signal": "Get trading signal for a symbol",
            "/api/stats/predictions": "Get pre-signal prediction accuracy stats",
            "/api/settings/lead-time": "Get/Update signal lead time (GET/POST)",
            "/api/active-signals": "Get currently active signals",
            "/docs": "API documentation"
        },
        "features": {
            "websocket": "Real-time price streaming from KuCoin",
            "execution": "Instant order execution with ±0.2% price tolerance",
            "delay_check": "Skip signals if delay > 2 seconds",
            "fallback": "Automatic REST API fallback if WebSocket fails",
            "async_processing": "Parallel processing for faster signal generation",
            "pre_signal_alerts": f"Early warning {lead_time}s before signal triggers (≥90% confidence)"
        },
        "monitored_pairs": ["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        "pre_signal_config": {
            "lead_time_seconds": lead_time,
            "min_confidence": "90%",
            "configurable": "Set SIGNAL_LEAD_TIME env var (20-60s)"
        },
        "disclaimer": "⚠️ RISK WARNING: Trading cryptocurrencies involves substantial risk of loss. Signals are for educational purposes only. Always do your own research and never invest more than you can afford to lose.",
        "data_source": "KuCoin API (WebSocket + REST)",
        "indicators": ["RSI-14", "EMA-12", "EMA-26"]
    }
