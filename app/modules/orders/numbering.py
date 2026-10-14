# backend/app/modules/orders/numbering.py
from __future__ import annotations

import re
import string

_SEQUENCE_RE = re.compile(r"^LE-\d{4}-(\d+)")

SUB_ORDER_SUFFIXES = string.ascii_lowercase


def order_sequence(order_number: str | None) -> int:
    """Numeric part of LE-YYYY-NNNNN, ignoring a sub-order suffix like "(a)"."""
    if not order_number:
        return 0
    match = _SEQUENCE_RE.match(str(order_number).strip())
    return int(match.group(1)) if match else 0


def sub_order_number(parent_number: str, index: int) -> str:
    """LE-2026-00412 + 0 -> LE-2026-00412(a)."""
    return f"{parent_number}({SUB_ORDER_SUFFIXES[index]})"
