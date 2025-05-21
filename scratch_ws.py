import os, json, websocket

API_KEY = os.environ["POLYGON_API_KEY"]           # same env-var you used before
ws = websocket.create_connection(
        "wss://socket.polygon.io/options", ping_interval=30)

print("→", ws.recv())                             # ① connected

ws.send(json.dumps({"action": "auth", "params": API_KEY}))
print("→", ws.recv())                             # ② auth_success

# subscribe ONLY ONE NBBO option so we're guaranteed traffic
ws.send(json.dumps({
    "action": "subscribe",
    "params": "NO.O:SPY250621C00591000"           # SPY 6 / 21 / 25 $591 strike
}))

while True:
    msg = ws.recv()
    print("→", msg)                               # should start printing quotes