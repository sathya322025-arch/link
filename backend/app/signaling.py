import json
import logging
from typing import Dict, List, Any
from datetime import datetime
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import RemoteSession, SessionEvent

logger = logging.getLogger("signaling")

class ConnectionManager:
    def __init__(self):
        # session_code -> {"admin": WebSocket, "client": WebSocket}
        self.active_rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_code: str, role: str):
        await websocket.accept()
        if session_code not in self.active_rooms:
            self.active_rooms[session_code] = {}
        
        self.active_rooms[session_code][role] = websocket
        logger.info(f"Peer connected: role={role} session={session_code}")

        # Notify other peer in the room
        other_role = "client" if role == "admin" else "admin"
        if other_role in self.active_rooms[session_code]:
            await self.send_to_peer(session_code, other_role, {
                "type": "peer_joined",
                "role": role,
                "timestamp": datetime.utcnow().isoformat()
            })

    def disconnect(self, session_code: str, role: str):
        if session_code in self.active_rooms:
            if role in self.active_rooms[session_code]:
                del self.active_rooms[session_code][role]
            if not self.active_rooms[session_code]:
                del self.active_rooms[session_code]
        logger.info(f"Peer disconnected: role={role} session={session_code}")

    async def send_to_peer(self, session_code: str, target_role: str, message: Dict[str, Any]):
        if session_code in self.active_rooms:
            recipient = self.active_rooms[session_code].get(target_role)
            if recipient:
                await recipient.send_text(json.dumps(message))

    async def broadcast_room(self, session_code: str, message: Dict[str, Any]):
        if session_code in self.active_rooms:
            for ws in self.active_rooms[session_code].values():
                await ws.send_text(json.dumps(message))

    async def handle_message(self, session_code: str, sender_role: str, data: Dict[str, Any]):
        msg_type = data.get("type")
        target_role = "client" if sender_role == "admin" else "admin"

        # WebRTC Signaling Messages: offer, answer, ice-candidate
        if msg_type in ["offer", "answer", "ice-candidate", "renegotiate"]:
            await self.send_to_peer(session_code, target_role, data)

        # Technical Support Controls: pointer, draw_line, clear_canvas, chat
        elif msg_type in ["pointer", "draw_line", "clear_canvas", "chat", "quality_update"]:
            await self.send_to_peer(session_code, target_role, data)

        # Session Lifecycle: pause, resume, terminate
        elif msg_type == "session_pause":
            self._update_session_status(session_code, "paused")
            await self.broadcast_room(session_code, {
                "type": "session_paused",
                "by": sender_role,
                "timestamp": datetime.utcnow().isoformat()
            })
            self._record_event(session_code, "session_paused", sender_role, data)

        elif msg_type == "session_resume":
            self._update_session_status(session_code, "active")
            await self.broadcast_room(session_code, {
                "type": "session_resumed",
                "by": sender_role,
                "timestamp": datetime.utcnow().isoformat()
            })
            self._record_event(session_code, "session_resumed", sender_role, data)

        elif msg_type == "session_terminate":
            reason = data.get("reason", "User or Admin requested termination")
            self._terminate_session(session_code, sender_role, reason)
            await self.broadcast_room(session_code, {
                "type": "session_terminated",
                "by": sender_role,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            })

    def _update_session_status(self, session_code: str, status: str):
        db: Session = SessionLocal()
        try:
            session = db.query(RemoteSession).filter(RemoteSession.session_code == session_code).first()
            if session:
                session.status = status
                if status == "paused":
                    session.paused_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    def _terminate_session(self, session_code: str, terminated_by: str, reason: str):
        db: Session = SessionLocal()
        try:
            session = db.query(RemoteSession).filter(RemoteSession.session_code == session_code).first()
            if session and session.status != "ended":
                session.status = "ended"
                session.ended_at = datetime.utcnow()
                session.terminated_by = terminated_by
                session.termination_reason = reason
                if session.started_at:
                    session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
                db.commit()
        finally:
            db.close()

    def _record_event(self, session_code: str, event_type: str, actor: str, payload: Dict[str, Any]):
        db: Session = SessionLocal()
        try:
            session = db.query(RemoteSession).filter(RemoteSession.session_code == session_code).first()
            if session:
                evt = SessionEvent(
                    session_id=session.id,
                    event_type=event_type,
                    actor=actor,
                    payload=payload
                )
                db.add(evt)
                db.commit()
        finally:
            db.close()

signaling_manager = ConnectionManager()

