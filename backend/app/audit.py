from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import AuditLog

def log_audit_event(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    actor_type: str = "admin",
    resource_type: str = "system",
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Creates an immutable audit log entry in the database."""
    log_entry = AuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {},
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

