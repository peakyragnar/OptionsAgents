#!/usr/bin/env python
"""Test the dashboard directly with live gamma data"""
import threading
import time
from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.dashboard.web_dashboard import run_dashboard
from src.persistence import get_latest_gamma

# Create engine
print("Creating engine...")
engine = GammaEngine(spx_price=5910.0)

# Override the get_dashboard_data to use our live gamma
original_get_dashboard_data = engine.get_dashboard_data

def get_dashboard_data_with_live_gamma():
    data = original_get_dashboard_data()
    
    # Get live gamma from database
    latest = get_latest_gamma()
    if latest:
        data['net_force'] = latest['gamma'] * -1  # Invert for dealer perspective
        data['stats']['live_dealer_gamma'] = latest['gamma']
        data['last_gamma_update'] = latest['time']
    
    return data

engine.get_dashboard_data = get_dashboard_data_with_live_gamma

# Start dashboard in thread
print("Starting dashboard on http://localhost:8080...")
dashboard_thread = threading.Thread(
    target=run_dashboard,
    args=(engine,),
    daemon=False
)
dashboard_thread.start()

print("\n✅ Dashboard is running at http://localhost:8080")
print("Press Ctrl+C to stop")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down...")