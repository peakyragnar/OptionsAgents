# src/stream/sinks.py
import atexit, datetime as _dt, pathlib as _pa
import pyarrow as pa, pyarrow.dataset as ds, pyarrow.parquet as pq

# ---------- CONFIG ----------
_FLUSH_EVERY = 2_000        # rows
_CODEC        = "zstd"      # fast + small
# ----------------------------

def _today_dir() -> _pa.Path:
    d = _dt.date.today().isoformat()              # '2025-05-21'
    path = _pa.Path(f"data/{d}")
    path.mkdir(parents=True, exist_ok=True)
    return path

class _ArrowSink:
    def __init__(self, filename: str, schema: pa.schema):
        self._file   = _today_dir() / filename
        self._schema = schema
        self._buf    = []                         # list[dict]

    # public -------------
    def append(self, row: dict) -> None:
        self._buf.append(row)
        if len(self._buf) >= _FLUSH_EVERY:
            self._flush()

    # private ------------
    def _flush(self) -> None:
        if not self._buf:
            return
        tbl = pa.Table.from_pylist(self._buf, schema=self._schema)
        pq.write_to_dataset(
            tbl,
            root_path=str(self._file),
            partition_cols=None, compression=_CODEC,
            existing_data_behavior="overwrite_or_ignore",
        )
        self._buf.clear()

    # make sure we never lose rows
    def _atexit(self):
        self._flush()

# ---- column definitions (adjust if your snapshot uses other names) ----
_quote_schema = pa.schema(
    [("ts", pa.timestamp("ns")),
     ("symbol", pa.string()),
     ("bid", pa.float64()),
     ("ask", pa.float64()),
     ("mid", pa.float64())]
)

_trade_schema = pa.schema(
    [("ts", pa.timestamp("ns")),
     ("symbol", pa.string()),
     ("price", pa.float64()),
     ("size", pa.int32()),
     ("side", pa.string())]      # "BUY"/"SELL"/"?"
)

# module-level singletons
quote_sink = _ArrowSink("quotes.parquet", _quote_schema)
trade_sink = _ArrowSink("trades.parquet", _trade_schema)

# one flush at interpreter shutdown
atexit.register(quote_sink._atexit)
atexit.register(trade_sink._atexit)