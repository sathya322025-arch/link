import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    AccessInvitation, AuthorizationRecord, RemoteSession, SessionEvent, Administrator, Device
)
from app.schemas import AuthorizeSessionRequest, SessionActionRequest, SessionResponse
from app.security import hash_token
from app.turn import get_ice_servers
from app.audit import log_audit_event
from app.routers.auth import get_current_admin
from app.signaling import signaling_manager

router = APIRouter(prefix="/sessions", tags=["Remote Sessions"])

@router.post("/authorize")
def authorize_session(
    req_body: AuthorizeSessionRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    User consent endpoint: Called when user confirms transparent screen-sharing consent.
    Converts valid invitation into an active remote session.
    """
    if not req_body.user_consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session cannot proceed without explicit user consent"
        )

    t_hash = hash_token(req_body.invitation_token)
    invitation = db.query(AccessInvitation).filter(AccessInvitation.token_hash == t_hash).first()

    if not invitation or invitation.is_revoked or invitation.expires_at <= datetime.utcnow() or invitation.current_uses >= invitation.max_uses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation link is invalid or expired")

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Increment invitation usage
    invitation.current_uses += 1

    # Generate session code
    session_code = f"SES-{secrets.token_hex(4).upper()}"

    # Create RemoteSession
    session = RemoteSession(
        session_code=session_code,
        invitation_id=invitation.id,
        device_id=invitation.target_device_id,
        admin_id=invitation.created_by_admin_id,
        user_id=invitation.target_user_id,
        status="connecting",
        started_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Record Authorization & User Consent Evidence
    auth_record = AuthorizationRecord(
        invitation_id=invitation.id,
        session_id=session.id,
        user_consent_given=True,
        screen_sharing_confirmed=True,
        client_ip=client_ip,
        user_agent=user_agent,
        permissions_granted=req_body.permissions_granted,
        consent_notice_text=req_body.consent_notice_text
    )
    db.add(auth_record)

    # Initial session event
    event = SessionEvent(
        session_id=session.id,
        event_type="consent_granted",
        actor="user",
        payload={
            "screen_info": req_body.client_screen_info,
            "permissions": req_body.permissions_granted
        }
    )
    db.add(event)
    db.commit()

    log_audit_event(
        db, action="SESSION_AUTHORIZED", actor_id=invitation.target_user_id, actor_type="user",
        resource_type="session", resource_id=session.id, ip_address=client_ip, user_agent=user_agent,
        details={"session_code": session_code, "purpose": invitation.session_purpose}
    )

    ice_servers = get_ice_servers(username_prefix=session_code)

    return {
        "status": "authorized",
        "session_id": session.id,
        "session_code": session.session_code,
        "ice_servers": ice_servers
    }

@router.get("/active")
def list_active_sessions(
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    sessions = db.query(RemoteSession).filter(
        RemoteSession.status.in_(["connecting", "active", "paused"])
    ).order_by(RemoteSession.started_at.desc()).all()

    results = []
    for s in sessions:
        admin_name = s.admin.full_name if s.admin else "Unknown"
        user_name = s.user.full_name if s.user else "Anonymous User"
        dev_name = s.device.hostname if s.device else "Web Guest Device"
        results.append({
            "id": s.id,
            "session_code": s.session_code,
            "status": s.status,
            "started_at": s.started_at,
            "paused_at": s.paused_at,
            "duration_seconds": int((datetime.utcnow() - s.started_at).total_seconds()) if s.started_at else 0,
            "admin_name": admin_name,
            "user_name": user_name,
            "device_name": dev_name
        })
    return results

@router.get("/ice-servers")
def fetch_ice_servers(current_admin: Administrator = Depends(get_current_admin)):
    """Provides TURN/STUN configuration for authenticated administrator console."""
    return {"ice_servers": get_ice_servers(username_prefix=current_admin.id[:8])}

@router.get("/{session_id}")
def get_session_details(
    session_id: str,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    session = db.query(RemoteSession).filter(RemoteSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    events = db.query(SessionEvent).filter(SessionEvent.session_id == session_id).order_by(SessionEvent.recorded_at.asc()).all()

    return {
        "id": session.id,
        "session_code": session.session_code,
        "status": session.status,
        "started_at": session.started_at,
        "paused_at": session.paused_at,
        "ended_at": session.ended_at,
        "duration_seconds": session.duration_seconds,
        "admin_name": session.admin.full_name if session.admin else None,
        "user_name": session.user.full_name if session.user else None,
        "termination_reason": session.termination_reason,
        "events": [
            {"event_type": e.event_type, "actor": e.actor, "payload": e.payload, "recorded_at": e.recorded_at}
            for e in events
        ]
    }

@router.post("/{session_id}/action")
async def perform_session_action(
    session_id: str,
    action_req: SessionActionRequest,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    session = db.query(RemoteSession).filter(RemoteSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    action = action_req.action.lower()
    if action == "pause":
        session.status = "paused"
        session.paused_at = datetime.utcnow()
        await signaling_manager.broadcast_room(session.session_code, {
            "type": "session_paused", "by": "admin", "timestamp": datetime.utcnow().isoformat()
        })
    elif action == "resume":
        session.status = "active"
        await signaling_manager.broadcast_room(session.session_code, {
            "type": "session_resumed", "by": "admin", "timestamp": datetime.utcnow().isoformat()
        })
    elif action == "terminate":
        session.status = "ended"
        session.ended_at = datetime.utcnow()
        session.terminated_by = "admin"
        session.termination_reason = action_req.reason or "Closed by administrator"
        if session.started_at:
            session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
        await signaling_manager.broadcast_room(session.session_code, {
            "type": "session_terminated", "by": "admin", "reason": session.termination_reason
        })
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action '{action}'")

    db.commit()
    log_audit_event(
        db, action=f"SESSION_{action.upper()}", actor_id=current_admin.id, actor_type="admin",
        resource_type="session", resource_id=session.id, details={"reason": action_req.reason}
    )

    return {"status": "ok", "session_status": session.status}

