from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import vnpy.web.services as services

ws_router = APIRouter(prefix="/ws", tags=["ws"])


@ws_router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "event": "connected",
            "payload": {
                "channel": "events",
                "server_time": datetime.now().isoformat(timespec="seconds"),
            },
        }
    )

    try:
        while True:
            stats = services.quant_service.get_stats().model_dump()
            await websocket.send_json({"event": "cb_quant.stats", "payload": stats})
            await websocket.send_json(
                {
                    "event": "heartbeat",
                    "payload": {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    },
                }
            )
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
