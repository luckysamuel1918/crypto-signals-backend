import sys
import os

# Add the parent directory to the Python path so we can import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from backend.routes import router as routes_router

# Create FastAPI app for Vercel deployment
app = FastAPI(title="Lucky Signals Backend")

# Register routes
app.include_router(routes_router, prefix="/api", tags=["signals"])

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
        "indicators": ["RSI-14", "EMA-12", "EMA-26"],
        "deployment": "Vercel Serverless"
    }

# Vercel expects the FastAPI app to be accessible
# This is the entry point for Vercel
handler = app