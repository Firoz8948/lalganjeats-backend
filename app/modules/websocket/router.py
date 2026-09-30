# backend/app/modules/websocket/router.py
"""
WebSocket routes for live order tracking.

Connect:
  ws://host/api/v1/websocket/tracking/{order_id}?token=<JWT>

Server pushes:
  { "type": "track_update", "order_id": N, "data": <TrackOrderOut> }
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.modules.websocket.auth import user_from_token
from app.modules.websocket.manager import tracking_manager
from app.modules.tracking.service import get_track_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/websocket", tags=["WebSocket"])


def _initial_snapshot(order_id: int, token: str) -> tuple[str, object]:
    """
    Auth + first snapshot in a short-lived session, so an open socket never holds
    a pooled DB connection. Returns ("ok", data), ("error", detail) or ("unauthorized", None).
    """
    db = SessionLocal()
    try:
        user = user_from_token(db, token)
        if not user:
            return "unauthorized", None
        try:
            return "ok", get_track_snapshot(db, order_id, user).model_dump(mode="json")
        except HTTPException as exc:
            return "error", exc.detail
    finally:
        db.close()


@router.websocket("/tracking/{order_id}")
async def tracking_ws(
    websocket: WebSocket,
    order_id: int,
    token: str = Query(...),
):
    connected = False
    try:
        # Sync DB work must stay off the event loop: a stalled query here would
        # freeze every request the server is handling.
        outcome, result = await run_in_threadpool(_initial_snapshot, order_id, token)
        if outcome == "unauthorized":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if outcome == "error":
            await websocket.accept()
            await websocket.send_json({"type": "error", "detail": result})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await tracking_manager.connect(order_id, websocket)
        connected = True
        await websocket.send_json({
            "type": "track_update",
            "order_id": order_id,
            "data": result,
        })

        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() in ("ping", '{"type":"ping"}'):
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS tracking error order=%s", order_id)
    finally:
        if connected:
            await tracking_manager.disconnect(order_id, websocket)
