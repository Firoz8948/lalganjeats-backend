# backend/app/modules/websocket/broadcast.py
"""Push tracking snapshots to connected WS clients (safe from sync routes)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.modules.websocket.manager import tracking_manager

logger = logging.getLogger(__name__)


def _get_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            return None


def publish_tracking_update(order_id: int, snapshot: dict[str, Any]) -> None:
    """
    Call from sync code (e.g. getlocation POST).
    Schedules an async broadcast on the running uvicorn loop.
    """
    payload = {"type": "track_update", "order_id": order_id, "data": snapshot}
    loop = _get_loop()
    if loop is None or not loop.is_running():
        logger.debug("No running loop — skip WS publish for order %s", order_id)
        return
    asyncio.run_coroutine_threadsafe(
        tracking_manager.broadcast(order_id, payload),
        loop,
    )
