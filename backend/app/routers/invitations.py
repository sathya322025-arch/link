from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AccessInvitation, Administrator, User
from app.schemas import CreateInvitationRequest, InvitationResponse, ValidateInvitationResponse
from app.security import generate_secure_token, hash_token
from app.audit import log_audit_event
from app.routers.auth import get_current_admin
from app.config import settings

router = APIRouter(prefix="/invitations", tags=["Access Invitations"])

@router.post("", response_model=InvitationResponse)
def create_invitation(
    req_body: CreateInvitationRequest,
    request: Request,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    raw_token = generate_secure_token(32)
    t_hash = hash_token(raw_token)
    t_hint = raw_token[-6:]
    expires_at = datetime.utcnow() + timedelta(minutes=req_body.expires_in_minutes)

    # Optional target user creation or association
    target_user_id = None
    if req_body.target_user_email:
        user = db.query(User).filter(User.email == req_body.target_user_email.lower()).first()
        if not user:
            user = User(
                email=req_body.target_user_email.lower(),
                full_name=req_body.target_user_name or "Authorized Client",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        target_user_id = user.id

    invitation = AccessInvitation(
        token_hash=t_hash,
        token_hint=t_hint,
        target_user_id=target_user_id,
        target_device_id=req_body.target_device_id,
        created_by_admin_id=current_admin.id,
        session_purpose=req_body.session_purpose,
        permitted_actions=req_body.permitted_actions,
        expires_at=expires_at,
        max_uses=1,
        current_uses=0,
        is_revoked=False
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # Construct complete access URL
    # Using request base URL to handle localhost, custom domain, or IP dynamically
    base_url = str(request.base_url).rstrip("/")
    access_url = f"{base_url}/join/{raw_token}"

    client_ip = request.client.host if request.client else "unknown"
    log_audit_event(
        db, action="INVITATION_CREATED", actor_id=current_admin.id, actor_type="admin",
        resource_type="invitation", resource_id=invitation.id, ip_address=client_ip,
        details={
            "token_hint": t_hint,
            "purpose": req_body.session_purpose,
            "expires_at": expires_at.isoformat(),
            "target_user_email": req_body.target_user_email
        }
    )

    return InvitationResponse(
        id=invitation.id,
        token_hint=invitation.token_hint,
        session_purpose=invitation.session_purpose,
        permitted_actions=invitation.permitted_actions,
        expires_at=invitation.expires_at,
        is_revoked=invitation.is_revoked,
        access_url=access_url,
        created_at=invitation.created_at
    )

@router.get("", response_model=List[InvitationResponse])
def list_invitations(
    status_filter: Optional[str] = None, # 'active', 'expired', 'revoked'
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(AccessInvitation).order_by(AccessInvitation.created_at.desc())
    now = datetime.utcnow()

    if status_filter == "active":
        query = query.filter(AccessInvitation.is_revoked == False, AccessInvitation.expires_at > now, AccessInvitation.current_uses < AccessInvitation.max_uses)
    elif status_filter == "expired":
        query = query.filter(AccessInvitation.expires_at <= now)
    elif status_filter == "revoked":
        query = query.filter(AccessInvitation.is_revoked == True)

    invitations = query.limit(50).all()
    return [
        InvitationResponse(
            id=inv.id,
            token_hint=inv.token_hint,
            session_purpose=inv.session_purpose,
            permitted_actions=inv.permitted_actions,
            expires_at=inv.expires_at,
            is_revoked=inv.is_revoked,
            access_url=None, # Raw token is never stored in DB and cannot be leaked back from list
            created_at=inv.created_at
        )
        for inv in invitations
    ]

@router.post("/{invitation_id}/revoke")
def revoke_invitation(
    invitation_id: str,
    request: Request,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    invitation = db.query(AccessInvitation).filter(AccessInvitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    invitation.is_revoked = True
    invitation.revoked_at = datetime.utcnow()
    db.commit()

    client_ip = request.client.host if request.client else "unknown"
    log_audit_event(
        db, action="INVITATION_REVOKED", actor_id=current_admin.id, actor_type="admin",
        resource_type="invitation", resource_id=invitation.id, ip_address=client_ip,
        details={"token_hint": invitation.token_hint}
    )

    return {"message": "Invitation successfully revoked", "id": invitation_id}

@router.get("/validate/{raw_token}", response_model=ValidateInvitationResponse)
def validate_token(raw_token: str, db: Session = Depends(get_db)):
    """Public endpoint called by the client UI upon loading the invitation link."""
    t_hash = hash_token(raw_token)
    invitation = db.query(AccessInvitation).filter(AccessInvitation.token_hash == t_hash).first()

    if not invitation:
        return ValidateInvitationResponse(valid=False, error="Invalid support access link")

    if invitation.is_revoked:
        return ValidateInvitationResponse(valid=False, error="This support link was revoked by an administrator")

    if invitation.expires_at <= datetime.utcnow():
        return ValidateInvitationResponse(valid=False, error="This support link has expired")

    if invitation.current_uses >= invitation.max_uses:
        return ValidateInvitationResponse(valid=False, error="This single-use access link has already been used")

    admin = db.query(Administrator).filter(Administrator.id == invitation.created_by_admin_id).first()
    admin_name = admin.full_name if admin else "Authorized Technical Administrator"

    return ValidateInvitationResponse(
        valid=True,
        invitation_id=invitation.id,
        admin_name=admin_name,
        session_purpose=invitation.session_purpose,
        permitted_actions=invitation.permitted_actions,
        expires_at=invitation.expires_at
    )

