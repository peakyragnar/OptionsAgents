#!/usr/bin/env python3
"""
Test Polygon Options WebSocket - what you actually have access to
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
                    
                    # Subscribe after auth success
                    if msg.get('status') == 'auth_success':
                        print("🚀 Subscribing to SPX index and high-volume SPX options...")
                        # Subscribe to SPX index and some liquid SPX options
                        symbols = [
                            "I:SPX",  # SPX Index
                            "O:SPXW250523C05800000",  # ATM call
                            "O:SPXW250523P05800000",  # ATM put
                        ]
                        # Try both formats
                        symbols_with_prefix = [f"T.{sym}" for sym in symbols]
                        params = ",".join(symbols_with_prefix)
                        print(f"📡 Testing with T. prefix: {symbols_with_prefix}")
                        ws.send(json.dumps({"action": "subscribe", "params": params}))
                        print(f"📡 Subscribed to: {symbols}")
                        print("⏰ Waiting 30 seconds for subscription confirmations...")
                        
                elif event_type == 'T':  # Trade
                    symbol = msg.get('sym')
                    price = msg.get('p')
                    size = msg.get('s')
                    print(f"🚀🚀🚀 TRADE: {symbol} @ ${price} x{size} 🚀🚀🚀")
                    
                elif event_type == 'status' and 'success' in msg.get('message', ''):
                    print(f"✅ SUBSCRIPTION CONFIRMED: {msg.get('message')}")
                    
                elif event_type == 'status' and 'error' in msg.get('message', '').lower():
                    print(f"❌ SUBSCRIPTION ERROR: {msg.get('message')}")
                    
                elif event_type in ['V', 'AM', 'A']:  # Value/Aggregate
                    symbol = msg.get('sym')
                    if symbol == 'I:SPX':
                        value = msg.get('val') or msg.get('c')
                        print(f"📊 SPX UPDATE: {value}")
                    
                else:
                    print(f"🔍 {timestamp} | {event_type}: {msg}")
                    
    except Exception as e:
        print(f"🔍 {timestamp} | ERROR: {e}")

def on_error(ws, error):
    print(f"❌ Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"🔌 Closed: {close_status_code}")

def on_open(ws):
    print("🔌 Connected to Polygon Options WebSocket")
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ POLYGON_API_KEY not set!")
        return
    auth_msg = {"action": "auth", "params": api_key}
    ws.send(json.dumps(auth_msg))

def main():
    # Use OPTIONS WebSocket (what you have access to)
    ws_url = "wss://socket.polygon.io/options"
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    
    print("🧪 Testing Polygon OPTIONS WebSocket...")
    print("   Testing SPX index + ATM options")
    print("   Should see SPX updates and option trades")
    
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped")

if __name__ == "__main__":
    main()
