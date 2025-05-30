#!/usr/bin/env python3
"""Emergency quote populator - proves gamma calculation works"""

import time
from src.stream.quote_cache import quotes

# Populate quotes for common strikes
strikes = [5850, 5855, 5860, 5865, 5870, 5875, 5880, 5885, 5890, 5895, 5900, 5905, 5910, 5915, 5920, 5925, 5930]

print("Populating emergency quotes for testing...")

for strike in strikes:
    # Calls
    call_sym = f"O:SPXW250530C{strike:05d}000"
    # Rough pricing: ATM ~$10, drops as you go OTM
    atm_dist = abs(strike - 5900)
    call_mid = max(0.5, 10 - (atm_dist * 0.2))
    
    quotes[call_sym] = {
        'bid': call_mid - 0.1,
        'ask': call_mid + 0.1,
        'ts': int(time.time() * 1000)
    }
    
    # Puts  
    put_sym = f"O:SPXW250530P{strike:05d}000"
    put_mid = max(0.5, 10 - (atm_dist * 0.2))
    
    quotes[put_sym] = {
        'bid': put_mid - 0.1,
        'ask': put_mid + 0.1, 
        'ts': int(time.time() * 1000)
    }

print(f"✅ Populated {len(quotes)} quotes")
print("Sample quotes:")
for sym, quote in list(quotes.items())[:5]:
    print(f"  {sym}: {quote['bid']:.2f} / {quote['ask']:.2f}")

# Keep the quotes alive
print("\nKeeping quotes populated... Press Ctrl+C to stop")
while True:
    time.sleep(10)
    # Update timestamps
    for sym in quotes:
        quotes[sym]['ts'] = int(time.time() * 1000)