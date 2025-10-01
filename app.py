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
telegram_app = None
telegram_task = None
scheduler = None

@app.on_event("startup")
async def startup_event():
    """Initialize Telegram bot and scheduler on FastAPI startup"""
    global telegram_app, telegram_task, scheduler
    
    # Setup Telegram messaging
    telegram_app = setup_telegram_bot()
    if telegram_app:
        print("🚀 Starting Telegram bot...")
        try:
            await telegram_app.initialize()
            await telegram_app.start()
            telegram_task = asyncio.create_task(telegram_app.updater.start_polling(drop_pending_updates=True))
            print("✅ Telegram bot started successfully")
        except Exception as e:
            print(f"❌ Telegram bot startup error: {e}")
    else:
        print("⚠️ Telegram bot not initialized - check credentials")
    
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
    """Clean shutdown of Telegram bot and scheduler"""
    global telegram_app, telegram_task, scheduler
    
    # Shutdown scheduler
    if scheduler:
        print("🛑 Shutting down scheduler...")
        scheduler.shutdown()
        print("✅ Scheduler stopped")
    
    # Shutdown Telegram bot
    if telegram_app:
        print("🛑 Shutting down Telegram bot...")
        try:
            if telegram_task:
                telegram_task.cancel()
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
            print("✅ Telegram bot stopped")
        except Exception as e:
            print(f"Error stopping Telegram bot: {e}")

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
