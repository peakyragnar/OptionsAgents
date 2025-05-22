import os, datetime as dt, zoneinfo, requests
from dotenv import load_dotenv

def fetch_spx_chain(expiry: str) -> list[str]:
    """
    Return ALL OCC tickers for SPX options expiring on <expiry>
    (yyyy-mm-dd) prefixed with 'T.' so they are ready for Polygon
    trade-channel subscription.
    """
    # Load environment variables
    load_dotenv()
    key = os.getenv("POLY_KEY") or os.getenv("POLYGON_KEY")
    if not key:
        raise RuntimeError("set $POLY_KEY (Polygon API key)")

    # Polygon now caps v3 'limit' at 120. Paginate with next_url.
    url = (f"https://api.polygon.io/v3/snapshot/options/SPX"
           f"?expiration_date={expiry}&limit=120&apiKey={key}")

    out = []
    while url:
        # Add API key to next_url if it doesn't have one
        if "apiKey=" not in url:
            separator = "&" if "?" in url else "?"
            url += f"{separator}apiKey={key}"
            
        response = requests.get(url, timeout=30)
        r = response.json()
        if r.get("status") != "OK":
            raise RuntimeError(f"Polygon error: {r.get('error', r)}")

        results = r.get("results", [])
        out += [f"T.{row['details']['ticker']}" for row in results]
        url  = r.get("next_url")      # None when finished
    return out