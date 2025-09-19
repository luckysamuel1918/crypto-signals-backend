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
- Backend server running on port 5000
- Uses KuCoin public API (no authentication required)
- Configured for Replit environment with proper host binding

## Architecture
- RESTful API design
- Modular structure with separate services
- Technical indicators: RSI (14-period) and EMA (12/26-period)
- Risk management with configurable take-profit (2%) and stop-loss (1%) levels

## Recent Changes
- Fixed import issues and type hints
- Configured workflow for Replit environment
- Set up proper host binding for public access