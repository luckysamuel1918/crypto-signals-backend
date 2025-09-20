# Lucky Signals Backend

## Overview
This is a FastAPI backend application that provides cryptocurrency trading signals using the KuCoin API. The application analyzes price data and generates BUY/SELL/HOLD signals based on RSI and EMA indicators.

## Project Structure
- `app.py` - FastAPI application entry point
- `backend/routes.py` - API route handlers
- `backend/signals.py` - Signal generation logic with RSI and EMA calculations
- `backend/kucoin_service.py` - KuCoin API integration for fetching price data
- `backend/strategy.py` - Strategy wrapper functions
- `pyproject.toml` - Python dependencies managed via uv

## API Endpoints
- `GET /` - Health check endpoint
- `GET /api/signal` - Get trading signal for a symbol
  - Parameters:
    - `symbol` (optional): Trading pair symbol (default: BTC-USDT)
    - `timeframe` (optional): Candle timeframe (default: 1hour)

## Dependencies
- fastapi - Web framework
- uvicorn - ASGI server  
- python-dotenv - Environment variable management
- requests - HTTP client for KuCoin API calls
- python-telegram-bot - Optional Telegram notifications
- apscheduler - Automated signal scheduling
- kucoin-python - KuCoin API client library

## Current Setup (Development)
- Backend API server running on port 8000 via uvicorn
- Uses KuCoin public API (no authentication required for price data)
- Configured for Replit environment with proper host binding (0.0.0.0:8000)
- Dependencies managed via uv package manager
- Virtual environment created at .pythonlibs/

## Production Deployment
- Deployment target: autoscale (scales automatically based on traffic)
- Production command: `uv run uvicorn app:app --host 0.0.0.0`
- Suitable for RESTful API with HTTP requests
- No port specification needed (handled by Replit's infrastructure)

## Architecture
- RESTful API design with FastAPI
- Modular structure with separate services and routes
- Technical indicators: RSI (14-period) and EMA (12/26-period)
- Risk management with dynamic take-profit and stop-loss calculations
- Optional Telegram bot integration for automated notifications
- Multithreaded signal generation for batch processing

## Recent Changes (GitHub Import Setup - Sept 20, 2025)
- ✅ Installed Python 3.11 and uv package manager
- ✅ Installed all dependencies via pyproject.toml using `uv sync`
- ✅ Configured Backend API workflow running on port 8000
- ✅ Verified all API endpoints functional:
  - GET / - API information and health check
  - GET /api/signal - Real-time trading signals with BTC-USDT
  - GET /docs - Interactive API documentation (Swagger UI)
- ✅ Configured autoscale deployment for production
- ✅ Updated documentation to reflect current setup