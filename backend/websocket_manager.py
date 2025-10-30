import asyncio
import json
import time
from typing import Dict, Optional, Callable, Set
import websockets
from datetime import datetime
import requests

class WebSocketPriceManager:
    def __init__(self):
        self.ws_url = "wss://ws-api-spot.kucoin.com"
        self.rest_api_base = "https://api.kucoin.com"
        self.websocket = None
        self.is_connected = False
        self.subscribed_symbols: Set[str] = set()
        self.price_callbacks: Dict[str, Callable] = {}
        self.last_prices: Dict[str, float] = {}
        self.connection_task = None
        self.use_fallback = False
        self.fallback_task = None
        
    async def start(self):
        """Start WebSocket connection with auto-reconnect"""
        print("🌐 Starting WebSocket Price Manager...")
        self.connection_task = asyncio.create_task(self._maintain_connection())
        
    async def stop(self):
        """Stop WebSocket connection"""
        print("🛑 Stopping WebSocket Price Manager...")
        if self.connection_task:
            self.connection_task.cancel()
        if self.fallback_task:
            self.fallback_task.cancel()
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False
        
    def _get_ws_token(self) -> Dict:
        """Get WebSocket connection token from KuCoin"""
        try:
            response = requests.post(
                f"{self.rest_api_base}/api/v1/bullet-public",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "200000":
                raise RuntimeError(f"Failed to get WS token: {data}")
                
            return data["data"]
        except Exception as e:
            print(f"❌ Error getting WebSocket token: {e}")
            raise
            
    async def _maintain_connection(self):
        """Maintain WebSocket connection with auto-reconnect"""
        while True:
            try:
                # Get connection token
                token_data = await asyncio.to_thread(self._get_ws_token)
                token = token_data["token"]
                
                # Get endpoint (KuCoin provides multiple servers)
                endpoint = token_data["instanceServers"][0]["endpoint"]
                connect_id = int(time.time() * 1000)
                ws_url = f"{endpoint}?token={token}&connectId={connect_id}"
                
                print(f"🔌 Connecting to KuCoin WebSocket...")
                
                async with websockets.connect(ws_url) as websocket:
                    self.websocket = websocket
                    self.is_connected = True
                    self.use_fallback = False
                    print("✅ WebSocket connected successfully")
                    
                    # Stop fallback if it was running
                    if self.fallback_task and not self.fallback_task.done():
                        self.fallback_task.cancel()
                        self.fallback_task = None
                    
                    # Resubscribe to all symbols
                    await self._resubscribe_all()
                    
                    # Listen for messages
                    await self._listen(websocket)
                    
            except Exception as e:
                print(f"❌ WebSocket connection error: {e}")
                self.is_connected = False
                
                # Start fallback mechanism
                if not self.use_fallback:
                    print("🔄 Switching to REST API fallback...")
                    self.use_fallback = True
                    if not self.fallback_task or self.fallback_task.done():
                        self.fallback_task = asyncio.create_task(self._fallback_polling())
                
                print("⏳ Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
                
    async def _fallback_polling(self):
        """Fallback to REST API polling when WebSocket is down"""
        print("📡 Starting REST API fallback polling (1-second interval)...")
        
        while self.use_fallback:
            try:
                for symbol in self.subscribed_symbols:
                    try:
                        # Fetch price via REST API
                        response = await asyncio.to_thread(
                            requests.get,
                            f"{self.rest_api_base}/api/v1/market/orderbook/level1?symbol={symbol}",
                            timeout=5
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        if data.get("code") == "200000":
                            price = float(data["data"]["price"])
                            timestamp = int(data["data"]["time"])
                            
                            # Update last price
                            self.last_prices[symbol] = price
                            
                            # Call callback
                            if symbol in self.price_callbacks:
                                await self.price_callbacks[symbol](symbol, price, timestamp)
                                
                    except Exception as e:
                        print(f"⚠️ Fallback polling error for {symbol}: {e}")
                        
                # Wait 1 second before next poll
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Fallback polling error: {e}")
                await asyncio.sleep(1)
                
    async def _resubscribe_all(self):
        """Resubscribe to all symbols after reconnection"""
        for symbol in self.subscribed_symbols:
            await self._send_subscribe(symbol)
            
    async def _send_subscribe(self, symbol: str):
        """Send subscription message for a symbol"""
        if not self.websocket or not self.is_connected:
            return
            
        subscribe_message = {
            "id": int(time.time() * 1000),
            "type": "subscribe",
            "topic": f"/market/ticker:{symbol}",
            "privateChannel": False,
            "response": True
        }
        
        try:
            await self.websocket.send(json.dumps(subscribe_message))
            print(f"📊 Subscribed to {symbol} ticker updates")
        except Exception as e:
            print(f"❌ Failed to subscribe to {symbol}: {e}")
            
    async def _listen(self, websocket):
        """Listen for WebSocket messages"""
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Handle different message types
                if data.get("type") == "welcome":
                    print("👋 WebSocket welcome message received")
                    
                elif data.get("type") == "ack":
                    print(f"✅ Subscription acknowledged: {data.get('id')}")
                    
                elif data.get("type") == "message":
                    # Price update message
                    topic = data.get("topic", "")
                    if "/market/ticker:" in topic:
                        await self._handle_price_update(data)
                        
                elif data.get("type") == "pong":
                    # Heartbeat response
                    pass
                    
            except Exception as e:
                print(f"❌ Error processing WebSocket message: {e}")
                
    async def _handle_price_update(self, data: Dict):
        """Handle price update from WebSocket"""
        try:
            topic = data.get("topic", "")
            symbol = topic.split(":")[-1]
            
            price_data = data.get("data", {})
            price = float(price_data.get("price", 0))
            timestamp = int(data.get("data", {}).get("time", 0))
            
            if price > 0:
                # Update last price
                self.last_prices[symbol] = price
                
                # Call registered callback
                if symbol in self.price_callbacks:
                    await self.price_callbacks[symbol](symbol, price, timestamp)
                    
        except Exception as e:
            print(f"❌ Error handling price update: {e}")
            
    async def subscribe(self, symbol: str, callback: Callable):
        """
        Subscribe to price updates for a symbol
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            callback: Async function to call on price update (symbol, price, timestamp)
        """
        symbol = symbol.upper()
        self.subscribed_symbols.add(symbol)
        self.price_callbacks[symbol] = callback
        
        # Subscribe via WebSocket if connected
        if self.is_connected and self.websocket:
            await self._send_subscribe(symbol)
        
        print(f"✅ Registered price callback for {symbol}")
        
    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get last known price for a symbol"""
        return self.last_prices.get(symbol.upper())
        
    async def ping_pong(self):
        """Send periodic ping to keep connection alive"""
        while self.is_connected:
            try:
                if self.websocket:
                    ping_message = {
                        "id": int(time.time() * 1000),
                        "type": "ping"
                    }
                    await self.websocket.send(json.dumps(ping_message))
                    
                await asyncio.sleep(30)  # Ping every 30 seconds
                
            except Exception as e:
                print(f"⚠️ Ping error: {e}")
                await asyncio.sleep(5)
