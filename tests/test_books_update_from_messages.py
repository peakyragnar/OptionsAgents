import json, importlib
from pathlib import Path
from src.stream import ws_client as w

def test_books_update_from_messages():
    # reset in-memory books
    importlib.reload(w)                   # clears quotes & pos dicts
    msgs = json.loads(Path("tests/fixtures/messages.json").read_text())
    for m in msgs:
        if m["ev"] == "QO":
            w.quotes[m["sym"]] = (m["bp"], m["ap"])
        elif m["ev"] == "TO":
            side = w.side_from_price(m["sym"], m["p"])
            if side == "buy":
                w.pos_long[m["sym"]]  += m["s"]
            elif side == "sell":
                w.pos_short[m["sym"]] += m["s"]

    tkr = "O:SPX240620C06000000"
    assert w.pos_long[tkr]  == 12
    assert w.pos_short[tkr] == 8