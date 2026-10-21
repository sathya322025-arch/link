from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SecurityPolicy, Administrator
from app.schemas import PolicyUpdate
from app.routers.auth import get_current_admin
from app.audit import log_audit_event

router = APIRouter(prefix="/policies", tags=["Security Policies"])

@router.get("")
def list_policies(
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    policies = db.query(SecurityPolicy).all()
    return {p.policy_key: {"value": p.policy_value, "description": p.description} for p in policies}

@router.put("/{policy_key}")
def update_policy(
    policy_key: str,
    update_req: PolicyUpdate,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if current_admin.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Super Administrators can modify security policies")

    policy = db.query(SecurityPolicy).filter(SecurityPolicy.policy_key == policy_key).first()
    if not policy:
        policy = SecurityPolicy(
            policy_key=policy_key,
            policy_value=update_req.policy_value,
            description=update_req.description,
            updated_by_admin_id=current_admin.id
        )
        db.add(policy)
    else:
        policy.policy_value = update_req.policy_value
        if update_req.description:
            policy.description = update_req.description
        policy.updated_by_admin_id = current_admin.id

    db.commit()

    log_audit_event(
        db, action="SECURITY_POLICY_UPDATED", actor_id=current_admin.id,
        actor_type="admin", resource_type="policy", resource_id=policy_key,
        details={"new_value": update_req.policy_value}
    )

    return {"status": "updated", "policy_key": policy_key}

