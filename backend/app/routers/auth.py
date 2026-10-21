from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Administrator
from app.schemas import LoginRequest, TokenResponse, AdminResponse
from app.security import (
    verify_password,
    create_access_token,
    decode_access_token,
    verify_totp,
    security_bearer,
    get_password_hash
)
from app.audit import log_audit_event
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_current_admin(
    credentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Administrator:
    payload = decode_access_token(credentials.credentials)
    admin_id: str = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    admin = db.query(Administrator).filter(Administrator.id == admin_id).first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator account inactive or not found")
    return admin

@router.post("/login", response_model=TokenResponse)
def login(login_req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    admin = db.query(Administrator).filter(Administrator.email == login_req.email.lower()).first()
    if not admin or not admin.is_active:
        log_audit_event(
            db, action="ADMIN_LOGIN_FAILED", actor_type="system",
            resource_type="auth", ip_address=client_ip, user_agent=user_agent,
            details={"email": login_req.email, "reason": "User not found or inactive"}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # Check lockout
    if admin.locked_until and admin.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to consecutive failed attempts. Try again later."
        )

    if not verify_password(login_req.password, admin.password_hash):
        admin.failed_login_attempts += 1
        if admin.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            admin.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_MINUTES)
        db.commit()
        log_audit_event(
            db, action="ADMIN_LOGIN_FAILED", actor_id=admin.id, actor_type="admin",
            resource_type="auth", ip_address=client_ip, user_agent=user_agent,
            details={"email": admin.email, "attempts": admin.failed_login_attempts}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # MFA Check
    if admin.mfa_enabled:
        if not login_req.totp_code:
            temp_token = create_access_token({"sub": admin.id, "mfa_pending": True}, timedelta(minutes=5))
            return TokenResponse(
                access_token="",
                mfa_required=True,
                temp_token=temp_token
            )
        # Verify code
        if not verify_totp(admin.mfa_secret, login_req.totp_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA / TOTP code")

    # Successful Login: Reset failed attempts & update last login
    admin.failed_login_attempts = 0
    admin.locked_until = None
    admin.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token({"sub": admin.id, "role": admin.role, "email": admin.email})
    log_audit_event(
        db, action="ADMIN_LOGIN_SUCCESS", actor_id=admin.id, actor_type="admin",
        resource_type="auth", ip_address=client_ip, user_agent=user_agent,
        details={"email": admin.email, "role": admin.role}
    )

    return TokenResponse(
        access_token=token,
        mfa_required=False,
        admin={
            "id": admin.id,
            "email": admin.email,
            "full_name": admin.full_name,
            "role": admin.role,
            "mfa_enabled": admin.mfa_enabled
        }
    )

@router.get("/me", response_model=AdminResponse)
def get_me(current_admin: Administrator = Depends(get_current_admin)):
    return current_admin

