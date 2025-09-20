# Lucky Signals Backend

## Overview
This is a FastAPI backend application that provides cryptocurrency trading signals using the KuCoin API. The application analyzes price data and generates BUY/SELL/HOLD signals based on RSI and EMA indicators.

## Project Structure
- `backend/main.py` - FastAPI application entry point
- `backend/routes.py` - API route handlers
- `backend/signals.py` - Signal generation logic with RSI and EMA calculations
- `backend/kucoin_service.py` - KuCoin API integration for fetching price data
- `backend/strategy.py` - Strategy wrapper functions
- `backend/requirements.txt` - Python dependencies

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

## Current Setup
- Backend server running on port 5000 via uvicorn
- Uses KuCoin public API (no authentication required)
- Configured for Replit environment with proper host binding (0.0.0.0:5000)
- Deployment configured for autoscale production environment
- Main entry point: app.py (removed duplicate backend/main.py)

## Architecture
- RESTful API design
- Modular structure with separate services
- Technical indicators: RSI (14-period) and EMA (12/26-period)
- Risk management with configurable take-profit (2%) and stop-loss (1%) levels
- Optional Telegram bot integration for notifications

## Recent Changes (Replit Import Setup)
- Installed dependencies via uv/pyproject.toml
- Fixed duplicate function definition in signals.py
- Removed duplicate backend/main.py file
- Set up workflow "Backend API" running uvicorn on port 5000
- Configured deployment for autoscale production
- Verified API endpoints working correctly (/api/signal and root)