from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog, Administrator
from app.schemas import AuditLogResponse
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/audit-logs", tags=["Audit & Compliance"])

@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    return query.offset(offset).limit(limit).all()

