#!/usr/bin/env python3
"""
Simple Polygon WebSocket test to verify connection works
"""
import json
import websocket
import os
from datetime import datetime

def on_message(ws, message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    try:
        data = json.loads(message)
        if isinstance(data, list):
            for msg in data:
                event_type = msg.get('ev', 'unknown')
                if event_type == 'status':
                    print(f"🔍 {timestamp} | STATUS: {msg.get('status')} - {msg.get('message', '')}")
                    
                    # Subscribe after auth
                    if msg.get('status') == 'auth_success':
                        print("🚀 Subscribing to SPY...")
                        ws.send(json.dumps({"action": "subscribe", "params": "T.SPY"}))
                        
                elif event_type == 'T':
                    symbol = msg.get('sym')
                    price = msg.get('p')
                    size = msg.get('s')
                    print(f"🚀 TRADE: {symbol} @ ${price} x{size}")
                else:
                    print(f"🔍 {timestamp} | {event_type}: {msg}")
    except Exception as e:
        print(f"🔍 {timestamp} | ERROR: {e}")

def on_error(ws, error):
    print(f"❌ Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 Closed: {close_status_code}")

def on_open(ws):
    print("🔌 Connected to Polygon")
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ POLYGON_API_KEY not set!")
        return
    auth_msg = {"action": "auth", "params": api_key}
    ws.send(json.dumps(auth_msg))

def main():
    # Test with stocks WebSocket (more reliable than options)
    ws_url = "wss://socket.polygon.io/stocks"
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    
    print("🧪 Testing Polygon WebSocket with SPY stock...")
    print("   Should see trades within 30 seconds")
    
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped")

if __name__ == "__main__":
    main()
