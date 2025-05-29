# tests/test_ws_client_classify.py
from src.stream.ws_client import side_from_price, EPS

def test_side_classifier_basic(monkeypatch):
    # Use a local quotes dict to avoid interference
    tkr = "O:SPX240620C06000000"
    test_quotes = {
        tkr: (9.90, 10.10)
    }
    
    # Monkey patch the quotes dict
    monkeypatch.setattr("src.stream.ws_client.quotes", test_quotes)
    
    assert side_from_price(tkr, 10.10)         == "buy"
    assert side_from_price(tkr,  9.90)         == "sell"
    assert side_from_price(tkr, 10.00) is None
    assert side_from_price(tkr, 10.10 - EPS/2) == "buy"
    assert side_from_price(tkr,  9.90 + EPS/2) == "sell"