#!/usr/bin/env python3
"""
Debug WebSocket Messages - Add this to your streaming code
"""

import json
from datetime import datetime

def debug_websocket_message(raw_message):
    """Add this function to your WebSocket message handler"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    try:
        # Try to parse as JSON
        data = json.loads(raw_message)
        event_type = data.get('ev', 'unknown')
        
        print(f"🔍 {timestamp} | TYPE: {event_type}")
        
        # Handle different message types
        if event_type == 'status':
            status = data.get('status', 'unknown')
            message = data.get('message', '')
            print(f"   STATUS: {status} - {message}")
            
        elif event_type == 'T':  # Trade
            symbol = data.get('sym', 'unknown')
            price = data.get('p', 0)
            size = data.get('s', 0)
            print(f"   TRADE: {symbol} @ ${price} x{size}")
            
        elif event_type == 'Q':  # Quote
            symbol = data.get('sym', 'unknown')
            bid = data.get('bp', 0)
            ask = data.get('ap', 0)
            print(f"   QUOTE: {symbol} Bid=${bid} Ask=${ask}")
            
        elif event_type == 'A':  # Aggregate
            symbol = data.get('sym', 'unknown')
            close = data.get('c', 0)
            volume = data.get('v', 0)
            print(f"   AGG: {symbol} Close=${close} Vol={volume}")
            
        else:
            print(f"   DATA: {data}")
            
    except json.JSONDecodeError:
        print(f"🔍 {timestamp} | RAW: {raw_message}")
    except Exception as e:
        print(f"🔍 {timestamp} | ERROR: {e}")

# Add this to your existing WebSocket handler
def enhanced_message_handler(ws, message):
    """Replace your current message handler with this"""
    
    # Debug every message
    debug_websocket_message(message)
    
    # Your existing message processing logic here
    # (keep whatever you had before)
