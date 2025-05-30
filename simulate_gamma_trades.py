#!/usr/bin/env python3
"""
Simulate live SPX 0DTE option trades for testing Gamma Tool Sam
Generates realistic trade patterns based on typical market behavior
"""

import asyncio
import random
import time
from datetime import datetime
import numpy as np

from src.stream.trade_feed import TRADE_Q

class TradeSimulator:
    """Simulates realistic SPX 0DTE option trades"""
    
    def __init__(self):
        self.spx_price = 5905.77  # Starting SPX price
        self.running = False
        
        # Popular strikes around current SPX
        self.setup_strikes()
        
        # Simulation parameters
        self.base_rate = 2  # Base trades per second
        self.spike_probability = 0.05  # 5% chance of volume spike
        
    def setup_strikes(self):
        """Setup realistic strike prices"""
        # Generate strikes every 5 points
        base = round(self.spx_price / 5) * 5
        self.strikes = list(range(base - 50, base + 55, 5))
        
        # Weight strikes by proximity to ATM (more volume near SPX)
        distances = [abs(s - self.spx_price) for s in self.strikes]
        max_dist = max(distances)
        self.strike_weights = [1 - (d / max_dist) ** 2 for d in distances]
        
    def generate_trade(self):
        """Generate a realistic option trade"""
        # Pick weighted strike
        strike = random.choices(self.strikes, weights=self.strike_weights)[0]
        
        # Determine if call or put (slight bias based on strike position)
        if strike > self.spx_price:
            option_type = 'C' if random.random() > 0.3 else 'P'
        else:
            option_type = 'P' if random.random() > 0.3 else 'C'
            
        # Generate realistic trade size
        if random.random() < self.spike_probability:
            # Volume spike
            size = random.choice([50, 100, 200, 500])
        else:
            # Normal trade
            size = random.choices(
                [1, 5, 10, 25, 50],
                weights=[0.3, 0.3, 0.2, 0.15, 0.05]
            )[0]
            
        # Generate price based on simple approximation
        distance = abs(strike - self.spx_price)
        if option_type == 'C':
            price = max(0.10, (self.spx_price - strike) if strike < self.spx_price else distance * 0.1)
        else:
            price = max(0.10, (strike - self.spx_price) if strike > self.spx_price else distance * 0.1)
            
        # Add some noise
        price *= random.uniform(0.9, 1.1)
        
        # Create trade data
        today = datetime.now().strftime('%y%m%d')
        symbol = f"O:SPXW{today}{option_type}{strike*1000:08d}"
        
        return {
            'symbol': symbol,
            'price': round(price, 2),
            'size': size,
            'timestamp': int(time.time() * 1000),
            'conditions': [1],  # Regular trade
            'exchange': random.choice(['CBOE', 'PHLX', 'ISE'])
        }
        
    async def simulate_market_open(self):
        """Simulate heavier volume at market open"""
        print("🔔 Simulating market open surge...")
        
        # Generate 50-100 trades quickly
        for _ in range(random.randint(50, 100)):
            trade = self.generate_trade()
            await TRADE_Q.put(trade)
            await asyncio.sleep(0.02)  # 50 trades/second
            
    async def simulate_pin_formation(self, strike: int, size: int = 200):
        """Simulate large trades at a specific strike (pin formation)"""
        print(f"📌 Simulating pin formation at {strike}")
        
        # Generate several large trades at the pin strike
        for i in range(5):
            for option_type in ['C', 'P']:
                today = datetime.now().strftime('%y%m%d')
                symbol = f"O:SPXW{today}{option_type}{strike*1000:08d}"
                
                trade = {
                    'symbol': symbol,
                    'price': 2.50 * random.uniform(0.8, 1.2),
                    'size': size + random.randint(-50, 50),
                    'timestamp': int(time.time() * 1000),
                    'conditions': [1],
                    'exchange': 'CBOE'
                }
                
                await TRADE_Q.put(trade)
                await asyncio.sleep(0.5)
                
    async def run(self):
        """Main simulation loop"""
        self.running = True
        
        print(f"🎲 Starting trade simulation (SPX: ${self.spx_price:,.2f})")
        print("📊 Generating realistic 0DTE option trades...")
        
        # Simulate market open
        await self.simulate_market_open()
        
        trade_count = 0
        next_pin_time = time.time() + random.randint(30, 60)
        
        while self.running:
            try:
                # Random SPX movement
                self.spx_price += random.gauss(0, 0.5)
                
                # Check for pin formation
                if time.time() > next_pin_time:
                    # Pick a strike near current SPX for pin
                    pin_strike = round(self.spx_price / 5) * 5
                    await self.simulate_pin_formation(pin_strike)
                    next_pin_time = time.time() + random.randint(60, 120)
                
                # Generate normal trades
                trades_this_second = np.random.poisson(self.base_rate)
                
                for _ in range(trades_this_second):
                    trade = self.generate_trade()
                    await TRADE_Q.put(trade)
                    trade_count += 1
                    
                    if trade_count % 100 == 0:
                        print(f"📈 Generated {trade_count} trades...")
                        
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Simulation error: {e}")
                
    def stop(self):
        """Stop simulation"""
        self.running = False

async def main():
    print("""
    ════════════════════════════════════════════
          SPX 0DTE TRADE SIMULATOR
    ════════════════════════════════════════════
    
    Generating realistic option trades for testing
    Press Ctrl+C to stop
    """)
    
    simulator = TradeSimulator()
    
    try:
        await simulator.run()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping simulation...")
        simulator.stop()

if __name__ == "__main__":
    # This should be run alongside gamma tool sam
    print("⚠️  This simulator should be imported by the main system")
    print("It will populate the TRADE_Q with simulated trades")