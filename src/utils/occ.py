"""
Minimal OCC-ticker utilities for SPX/SPXW index options.

OCC sym format:  O:{root}{YY}{MM}{DD}{C/P}{strike*1000:08d}
Example:         O:SPXW250519P05000000
"""

from __future__ import annotations
import datetime as _dt
from typing import NamedTuple

class ParsedOCC(NamedTuple):
    root: str         # 'SPXW'
    expiry: _dt.date  # YYYY-MM-DD
    strike: int       # 5250 = 5250.00
    is_call: bool

def parse(symbol: str) -> ParsedOCC:
    if not symbol.startswith("O:"):
        raise ValueError(f"not an OCC symbol: {symbol}")
    body = symbol[2:]          # strip 'O:'
    root      = body[:-15]     # 'SPX' or 'SPXW'
    yy, mm, dd = body[-15:-9][:2], body[-13:-11], body[-11:-9]
    cp        = body[-9]       # 'C' or 'P'
    strike_x1000 = int(body[-8:])
    expiry = _dt.date(int("20" + yy), int(mm), int(dd))
    return ParsedOCC(root, expiry, strike_x1000 // 1000, cp == "C")