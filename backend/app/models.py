import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Administrator(Base):
    __tablename__ = "administrators"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(50), nullable=False, default="support_engineer") # 'superadmin', 'support_engineer', 'auditor'
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    created_invitations = relationship("AccessInvitation", back_populates="creator", foreign_keys="AccessInvitation.created_by_admin_id")
    remote_sessions = relationship("RemoteSession", back_populates="admin")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(150), nullable=False)
    department = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    devices = relationship("Device", back_populates="registered_user")
    invitations = relationship("AccessInvitation", back_populates="target_user")
    sessions = relationship("RemoteSession", back_populates="user")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_identifier = Column(String(128), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    os_type = Column(String(50), nullable=False) # 'windows', 'macos', 'linux', 'android', 'ios', 'browser_generic'
    os_version = Column(String(100), nullable=True)
    ip_address = Column(String(64), nullable=True)
    mac_address = Column(String(32), nullable=True)
    agent_version = Column(String(50), nullable=True)
    is_managed = Column(Boolean, default=False, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False, index=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    registered_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    registered_user = relationship("User", back_populates="devices")
    enrollments = relationship("DeviceEnrollment", back_populates="device", cascade="all, delete-orphan")
    sessions = relationship("RemoteSession", back_populates="device")


class DeviceEnrollment(Base):
    __tablename__ = "device_enrollments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    enrollment_token_hash = Column(String(128), nullable=False)
    enrolled_by_admin_id = Column(String(36), ForeignKey("administrators.id"), nullable=True)
    policy_profile = Column(String(100), default="standard_support", nullable=False)
    certificate_fingerprint = Column(String(128), nullable=True)
    status = Column(String(50), default="active", nullable=False) # 'pending', 'active', 'suspended', 'revoked'
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_admin_id = Column(String(36), ForeignKey("administrators.id"), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # Relationships
    device = relationship("Device", back_populates="enrollments")


class AccessInvitation(Base):
    __tablename__ = "access_invitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    token_hint = Column(String(8), nullable=False)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    created_by_admin_id = Column(String(36), ForeignKey("administrators.id"), nullable=False)
    session_purpose = Column(String(255), nullable=False)
    permitted_actions = Column(JSON, default=list, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    max_uses = Column(Integer, default=1, nullable=False)
    current_uses = Column(Integer, default=0, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    creator = relationship("Administrator", back_populates="created_invitations")
    target_user = relationship("User", back_populates="invitations")
    sessions = relationship("RemoteSession", back_populates="invitation")
    authorization_records = relationship("AuthorizationRecord", back_populates="invitation")


class RemoteSession(Base):
    __tablename__ = "remote_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_code = Column(String(32), unique=True, nullable=False, index=True)
    invitation_id = Column(String(36), ForeignKey("access_invitations.id", ondelete="SET NULL"), nullable=True)
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    admin_id = Column(String(36), ForeignKey("administrators.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="requested", nullable=False, index=True) # requested, connecting, active, paused, ended, rejected, expired
    started_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    termination_reason = Column(String(100), nullable=True)
    terminated_by = Column(String(50), nullable=True) # 'admin', 'user', 'timeout', 'network_disconnect'
    webrtc_connection_details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    invitation = relationship("AccessInvitation", back_populates="sessions")
    admin = relationship("Administrator", back_populates="remote_sessions")
    user = relationship("User", back_populates="sessions")
    device = relationship("Device", back_populates="sessions")
    events = relationship("SessionEvent", back_populates="session", cascade="all, delete-orphan")
    authorization_record = relationship("AuthorizationRecord", back_populates="session", uselist=False)


class AuthorizationRecord(Base):
    __tablename__ = "authorization_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invitation_id = Column(String(36), ForeignKey("access_invitations.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(36), ForeignKey("remote_sessions.id", ondelete="CASCADE"), nullable=False)
    user_consent_given = Column(Boolean, nullable=False)
    consent_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    screen_sharing_confirmed = Column(Boolean, default=False, nullable=False)
    permissions_granted = Column(JSON, default=list, nullable=False)
    signature_digest = Column(String(128), nullable=True)
    consent_notice_text = Column(Text, nullable=False)

    # Relationships
    invitation = relationship("AccessInvitation", back_populates="authorization_records")
    session = relationship("RemoteSession", back_populates="authorization_record")


class SessionEvent(Base):
    __tablename__ = "session_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("remote_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(50), nullable=False) # 'admin', 'user', 'system'
    payload = Column(JSON, default=dict, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("RemoteSession", back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_type = Column(String(50), nullable=False) # 'admin', 'user', 'device_agent', 'system'
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SecurityPolicy(Base):
    __tablename__ = "security_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    policy_key = Column(String(100), unique=True, nullable=False)
    policy_value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_by_admin_id = Column(String(36), ForeignKey("administrators.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

