from fastapi import FastAPI
from backend.routes import router as routes_router
from backend.signals import setup_telegram_bot, generate_scheduled_signals
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import os

app = FastAPI(title="Lucky Signals Backend")

# Register routes
app.include_router(routes_router, prefix="/api", tags=["signals"])

# Global variables
scheduler = None

@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on FastAPI startup"""
    global scheduler
    
    # Setup Telegram messaging (direct API calls, no bot polling)
    setup_telegram_bot()
    
    # Start APScheduler for automatic signal generation
    print("⏰ Starting signal scheduler...")
    scheduler = BackgroundScheduler()
    
    # Schedule signal generation every 15 minutes
    scheduler.add_job(
        generate_scheduled_signals,
        'interval',
        minutes=15,
        id='signal_generation',
        name='Generate crypto signals every 15 minutes',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Scheduler started - signals will be generated every 15 minutes")
    
    # Generate signals immediately on startup
    print("🚀 Generating initial signals...")
    generate_scheduled_signals()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of scheduler"""
    global scheduler
    
    # Shutdown scheduler
    if scheduler:
        print("🛑 Shutting down scheduler...")
        scheduler.shutdown()
        print("✅ Scheduler stopped")

@app.get("/")
def root():
    return {
        "message": "Lucky Signals Backend - Crypto Trading Signals API",
        "version": "2.0.0",
        "endpoints": {
            "/api/signal": "Get trading signal for a symbol",
            "/docs": "API documentation"
        },
        "disclaimer": "⚠️ RISK WARNING: Trading cryptocurrencies involves substantial risk of loss. Signals are for educational purposes only. Always do your own research and never invest more than you can afford to lose.",
        "data_source": "KuCoin API",
        "indicators": ["RSI-14", "EMA-12", "EMA-26"]
    }
