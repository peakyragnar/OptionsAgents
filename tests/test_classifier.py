from src.stream.ws_client import side_from_price, quotes, EPS

def test_classify_buy_sell():
    tkr = "O:SPX240620C06000000"
    # seed quote book
    quotes[tkr] = (9.90, 10.10)          # bid, ask

    assert side_from_price(tkr, 10.10) == "buy"     # hit ask
    assert side_from_price(tkr, 9.90)  == "sell"    # hit bid
    # mid-market → None
    assert side_from_price(tkr, 10.00) is None
    # tolerance works
    assert side_from_price(tkr, 10.10 - EPS/2) == "buy"
    assert side_from_price(tkr,  9.90 + EPS/2) == "sell"