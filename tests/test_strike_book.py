import math
from src.dealer.strike_book import StrikeBook, Side

def test_updates():
    b = StrikeBook()
    key = (5250, True)
    b.update(key, Side.BUY, 10, gamma=0.002)   # dealer short
    b.update(key, Side.SELL, 5,  gamma=0.001)  # dealer long
    row = b.row(key)
    assert row.open_long  == 10
    assert row.open_short == 5
    # net γ = –0.002*10 + 0.001*5 = –0.015
    assert math.isclose(row.net_gamma, -0.015, rel_tol=1e-12)
    assert math.isclose(b.total_gamma(), -0.015, rel_tol=1e-12)