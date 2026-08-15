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

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.database import SessionLocal
from app.modules.websocket.auth import user_from_token
from app.modules.websocket.manager import tracking_manager
from app.modules.tracking.service import get_track_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/websocket", tags=["WebSocket"])


@router.websocket("/tracking/{order_id}")
async def tracking_ws(
    websocket: WebSocket,
    order_id: int,
    token: str = Query(...),
):
    db: Session = SessionLocal()
    connected = False
    try:
        user = user_from_token(db, token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            snap = get_track_snapshot(db, order_id, user)
        except HTTPException as exc:
            await websocket.accept()
            await websocket.send_json({"type": "error", "detail": exc.detail})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await tracking_manager.connect(order_id, websocket)
        connected = True
        await websocket.send_json({
            "type": "track_update",
            "order_id": order_id,
            "data": snap.model_dump(mode="json"),
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
        db.close()
