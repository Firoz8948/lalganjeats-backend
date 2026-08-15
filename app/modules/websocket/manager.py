# backend/app/modules/websocket/manager.py
"""In-memory WebSocket room manager keyed by order_id."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TrackingConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, order_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(order_id, set()).add(websocket)
        logger.info("WS tracking connected order=%s clients=%s", order_id, len(self._rooms.get(order_id, ())))

    async def disconnect(self, order_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            clients = self._rooms.get(order_id)
            if not clients:
                return
            clients.discard(websocket)
            if not clients:
                self._rooms.pop(order_id, None)

    async def broadcast(self, order_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._rooms.get(order_id, set()))
        if not clients:
            return
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(order_id, ws)


tracking_manager = TrackingConnectionManager()
