from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth & Admin Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    temp_token: Optional[str] = None
    admin: Optional[Dict[str, Any]] = None

class AdminCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "support_engineer"

class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    mfa_enabled: bool
    is_active: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True

# --- Invitation Schemas ---
class CreateInvitationRequest(BaseModel):
    target_user_name: Optional[str] = None
    target_user_email: Optional[str] = None
    session_purpose: str = Field(..., min_length=3, max_length=255)
    target_device_id: Optional[str] = None
    permitted_actions: List[str] = ["screen_view", "live_pointer", "chat"]
    expires_in_minutes: int = Field(default=15, ge=5, le=1440)

class InvitationResponse(BaseModel):
    id: str
    token_hint: str
    session_purpose: str
    permitted_actions: List[str]
    expires_at: datetime
    is_revoked: bool
    access_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ValidateInvitationResponse(BaseModel):
    valid: bool
    invitation_id: Optional[str] = None
    admin_name: Optional[str] = None
    session_purpose: Optional[str] = None
    permitted_actions: List[str] = []
    expires_at: Optional[datetime] = None
    error: Optional[str] = None

# --- Session Consent & Lifecycle Schemas ---
class AuthorizeSessionRequest(BaseModel):
    invitation_token: str
    user_consent_given: bool
    consent_notice_text: str
    permissions_granted: List[str]
    client_screen_info: Optional[Dict[str, Any]] = None

class SessionActionRequest(BaseModel):
    action: str = Field(..., description="'pause', 'resume', 'terminate'")
    reason: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    session_code: str
    status: str
    started_at: Optional[datetime]
    paused_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: int
    admin_name: Optional[str] = None
    user_name: Optional[str] = None
    target_device_name: Optional[str] = None
    termination_reason: Optional[str] = None

    class Config:
        from_attributes = True

# --- Device Schemas ---
class DeviceResponse(BaseModel):
    id: str
    device_identifier: str
    hostname: str
    os_type: str
    os_version: Optional[str]
    ip_address: Optional[str]
    is_managed: bool
    is_online: bool
    last_heartbeat_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceEnrollmentRequest(BaseModel):
    hostname: str
    os_type: str
    os_version: Optional[str] = None
    device_identifier: str
    mac_address: Optional[str] = None
    enrollment_token: str

class DeviceHeartbeatRequest(BaseModel):
    device_identifier: str
    agent_version: str
    os_version: Optional[str] = None
    ip_address: Optional[str] = None
    active_user: Optional[str] = None

# --- Audit & Policy Schemas ---
class AuditLogResponse(BaseModel):
    id: str
    actor_id: Optional[str]
    actor_type: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    details: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True

class PolicyUpdate(BaseModel):
    policy_value: Dict[str, Any]
    description: Optional[str] = None
