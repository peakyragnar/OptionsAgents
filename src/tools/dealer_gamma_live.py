"""
Read latest intraday snapshot and return live dealer gamma summary.
"""
import glob, pandas as pd, numpy as np, datetime as dt

def dealer_gamma_live(path="data/intraday"):
    files = sorted(glob.glob(f"{path}/*.parquet"))
    if not files:
        raise RuntimeError("no intraday snapshot yet")
    df = pd.read_parquet(files[-1])
    total = df.gamma_usd.sum()
    flip  = abs(total) / (df.gamma_usd.abs().sum()/df.shape[0])  # crude flip est
    return dict(ts=files[-1][-15:-7],
                gamma_total = np.float64(total),
                gamma_flip  = round(flip, 1),
                detail = df)

if __name__ == "__main__":
    import pprint, sys; pprint.pprint(dealer_gamma_live())