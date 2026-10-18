"""HTTP + WebSocket routes for the M6.1 local web dashboard.

    GET  /web/health      backend status for the web UI (the M0 /health route is unchanged)
    WS   /ws/session      one isolated MADQAQ session per connection
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from apps.vision_demo.main import resolve_zones_path
from apps.web_api import config
from apps.web_api.protocol import ProtocolError, error_message, parse_command
from apps.web_api.session import SessionLimitError, SessionManager, disclosures
from sentinel.dual_channel.state import NoActiveJourneyError
from sentinel.vision.config import DEFAULT_ZONES_PATH
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

log = logging.getLogger("madqaq.web")
router = APIRouter()


def get_manager(app) -> SessionManager:
    manager = getattr(app.state, "web_sessions", None)
    if manager is None:
        manager = SessionManager(ZoneSet.load(resolve_zones_path(DEFAULT_ZONES_PATH)), procedure())
        app.state.web_sessions = manager
    return manager


@router.get("/web/health")
def web_health(request: Request):
    m = get_manager(request.app)
    return {
        "status": "ok",
        "service": "madqaq-sentinel-web",
        "protocol": config.PROTOCOL_VERSION,
        "engine_version": "m0.1",
        "active_sessions": m.count,
        "max_sessions": m.max_sessions,
        "digital_simulated": True,
        "websocket_support": websocket_support(),
        "disclosures": disclosures(),
    }


def websocket_support() -> bool:
    """uvicorn serves WebSockets only if `websockets` or `wsproto` is installed (pip install -e ".[web]")."""
    return any(importlib.util.find_spec(m) is not None for m in ("websockets", "wsproto"))


def _origin_allowed(ws: WebSocket) -> bool:
    """Browsers always send Origin; only the local frontend origins may open a session.
    Non-browser local clients (tests, tools) send no Origin and are allowed."""
    origin = ws.headers.get("origin")
    return origin is None or origin.rstrip("/") in config.allowed_origins()


@router.websocket("/ws/session")
async def session_socket(ws: WebSocket):
    if not _origin_allowed(ws):
        await ws.close(code=1008, reason="origin not allowed")
        return
    manager = get_manager(ws.app)
    try:
        session = manager.create()
    except SessionLimitError as exc:
        await ws.accept()
        await ws.send_json(error_message("session_limit", str(exc)))
        await ws.close(code=1013, reason="session limit")
        return
    await ws.accept()
    try:
        await ws.send_json({
            "type": "hello",
            "protocol": config.PROTOCOL_VERSION,
            "session_id": session.session_id,
            "zones": session.zones_payload(),
            "limits": {"max_frame_bytes": config.MAX_FRAME_BYTES, "max_frame_width": config.MAX_FRAME_WIDTH,
                       "max_frame_height": config.MAX_FRAME_HEIGHT, "max_text_bytes": config.MAX_TEXT_BYTES},
            "recommended": {"sample_fps": config.RECOMMENDED_SAMPLE_FPS, "max_width": config.RECOMMENDED_MAX_WIDTH,
                            "jpeg_quality": config.RECOMMENDED_JPEG_QUALITY},
            "digital_simulated": True,
            "disclosures": disclosures(),
        })
        await ws.send_json(session.state())
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            data, text = message.get("bytes"), message.get("text")
            if data is not None:
                await _handle_frame(ws, session, data)
            elif text is not None:
                await _handle_text(ws, session, text)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("web session %s failed", session.session_id)
    finally:
        manager.remove(session.session_id)


async def _handle_frame(ws: WebSocket, session, data: bytes) -> None:
    try:
        # Model inference runs off the event loop; frames of one session are processed one at a time.
        await asyncio.to_thread(session.process_jpeg, data)
    except ProtocolError as exc:
        await ws.send_json(error_message(exc.code, exc.message))
    await ws.send_json(session.state())
    session.notice = None


async def _handle_text(ws: WebSocket, session, text: str) -> None:
    try:
        command = parse_command(text)
    except ProtocolError as exc:
        await ws.send_json(error_message(exc.code, exc.message))
        return
    if command.name == "ping":
        await ws.send_json({"type": "pong", "session_id": session.session_id})
        return
    if command.name == "get_evidence":
        try:
            await ws.send_json({"type": "evidence", "evidence": session.evidence()})
        except NoActiveJourneyError as exc:
            await ws.send_json(error_message("no_journey", str(exc)))
        return
    ok, msg = session.apply(command)
    await ws.send_json({"type": "ack", "command": command.name, "ok": ok, "message": msg})
    await ws.send_json(session.state())
