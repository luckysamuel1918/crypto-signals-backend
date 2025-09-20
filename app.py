from fastapi import FastAPI
from backend.routes import router as routes_router
from backend.signals import setup_telegram_bot
import asyncio

app = FastAPI(title="Lucky Signals Backend")

# Register routes
app.include_router(routes_router, prefix="/api", tags=["signals"])

# Global variable to store the telegram bot application
telegram_app = None
telegram_task = None

@app.on_event("startup")
async def startup_event():
    """Initialize Telegram bot on FastAPI startup"""
    global telegram_app, telegram_task
    telegram_app = setup_telegram_bot()
    if telegram_app:
        print("🚀 Starting Telegram bot...")
        try:
            # Start the bot in the background using asyncio
            await telegram_app.initialize()
            await telegram_app.start()
            
            # Create a background task for polling
            telegram_task = asyncio.create_task(telegram_app.updater.start_polling(drop_pending_updates=True))
            print("✅ Telegram bot started successfully")
        except Exception as e:
            print(f"❌ Telegram bot startup error: {e}")
    else:
        print("⚠️ Telegram bot not initialized - check credentials")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of Telegram bot"""
    global telegram_app, telegram_task
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
    return {"message": "Backend is running successfully"}
