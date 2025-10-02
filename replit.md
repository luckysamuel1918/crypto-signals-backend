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

## Recent Changes (GitHub Import Setup - October 2, 2025)
- ✅ Fresh GitHub repository clone imported to Replit environment
- ✅ Python 3.11 environment verified and uv package manager available  
- ✅ All dependencies installed via pyproject.toml (fastapi, uvicorn, kucoin-python, etc.)
- ✅ Backend API workflow running on port 8000 with proper host binding (0.0.0.0:8000)
- ✅ Verified all API endpoints functional:
  - GET / - API information and health check ✅
  - GET /api/signal - Real-time trading signals (tested with BTC-USDT and ETH-USDT) ✅
  - GET /docs - Interactive API documentation (Swagger UI) available
- ✅ Security enhancement: Moved Telegram credentials from hardcoded values to environment variables
  - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID now loaded from environment
  - Graceful handling when credentials are not set
  - Fixed security vulnerability where credentials were exposed in source code
- ✅ Fixed LSP errors in app.py:
  - Removed unnecessary Telegram bot polling logic (app uses direct API calls)
  - Cleaned up unused global variables (telegram_app, telegram_task)
  - Simplified startup/shutdown event handlers
- ✅ Created .gitignore for Python project (excludes __pycache__, .pythonlibs/, .env, etc.)
- ✅ Configured autoscale deployment for production using uv and uvicorn
  - Deployment uses proper host binding (0.0.0.0) without hardcoded port
  - Replit automatically manages port allocation in production
- ✅ Application ready for use - all core functionality working
- ✅ Import process completed successfully

## Telegram Integration Setup

The application supports automatic Telegram notifications for trading signals. To enable this feature:

1. **Set up environment variables (Secure Method - Recommended):**
   - Go to the "Secrets" tab in Replit (lock icon in the sidebar)
   - Add the following secrets:
     - `TELEGRAM_BOT_TOKEN` = Your bot token from [@BotFather](https://t.me/BotFather)
     - `TELEGRAM_CHAT_ID` = Your Telegram chat ID
   
2. **How to get credentials:**
   - **Bot Token:** Message [@BotFather](https://t.me/BotFather) on Telegram, create a new bot with `/newbot`, and copy the token
   - **Chat ID:** Message [@userinfobot](https://t.me/userinfobot) on Telegram to get your chat ID

3. **Restart the application** after adding secrets to activate Telegram notifications

**Note:** If these credentials are not set, the application will continue to work normally for API calls, but Telegram notifications will be skipped with a warning message. This is intentional for security - credentials are never hardcoded in the source code.

## Automated Signal Generation

- **Scheduler:** APScheduler runs in the background
- **Frequency:** Signals are generated every 15 minutes automatically
- **Pairs Monitored:** BTC-USDT, ETH-USDT, BNB-USDT (configurable in `backend/signals.py`)
- **Notification Format:** Formatted alerts sent to Telegram with:
  - Signal type (BUY/SELL/HOLD) with emoji indicators
  - Entry price, take profit, and stop loss levels
  - Technical indicators (RSI, EMA12, EMA26)
  - Confidence score based on multi-timeframe analysis
  - Risk warning

## User Preferences
- Backend-only API application (no frontend component)
- Uses KuCoin API for cryptocurrency price data (real-time data, no mock values)
- Multi-timeframe analysis (15min, 1hour, 4hour) for 70-80% accuracy target
- Automatic signal generation every 15 minutes via APScheduler
- Optional Telegram integration for notifications (requires environment variables)