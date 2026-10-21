from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Device, DeviceEnrollment, Administrator
from app.schemas import DeviceResponse, DeviceEnrollmentRequest, DeviceHeartbeatRequest
from app.security import generate_secure_token, hash_token
from app.audit import log_audit_event
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/devices", tags=["Device Inventory & Enrollment"])

@router.get("", response_model=List[DeviceResponse])
def get_device_inventory(
    is_online: Optional[bool] = None,
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Device)
    if is_online is not None:
        query = query.filter(Device.is_online == is_online)
    return query.order_by(Device.last_heartbeat_at.desc().nullslast()).all()

@router.post("/enrollment-token")
def create_enrollment_token(
    policy_profile: str = "standard_support",
    current_admin: Administrator = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Generates a cryptographic enrollment token used by managed agents."""
    raw_token = f"ENROLL-{generate_secure_token(16)}"
    t_hash = hash_token(raw_token)

    # In production, temporary enrollment record is saved or signed via HMAC
    log_audit_event(
        db, action="DEVICE_ENROLLMENT_TOKEN_CREATED", actor_id=current_admin.id,
        actor_type="admin", resource_type="enrollment",
        details={"policy_profile": policy_profile, "token_hint": raw_token[-6:]}
    )

    return {
        "enrollment_token": raw_token,
        "policy_profile": policy_profile,
        "expires_in_hours": 24,
        "instructions": "Execute device_agent.py --enroll <token> on target managed machine."
    }

@router.post("/register")
def register_device(
    reg_req: DeviceEnrollmentRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Called by native agent during initial provisioning."""
    client_ip = request.client.host if request.client else "unknown"

    device = db.query(Device).filter(Device.device_identifier == reg_req.device_identifier).first()
    if not device:
        device = Device(
            device_identifier=reg_req.device_identifier,
            hostname=reg_req.hostname,
            os_type=reg_req.os_type,
            os_version=reg_req.os_version,
            ip_address=client_ip,
            mac_address=reg_req.mac_address,
            is_managed=True,
            is_online=True,
            last_heartbeat_at=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.hostname = reg_req.hostname
        device.os_version = reg_req.os_version
        device.ip_address = client_ip
        device.is_online = True
        device.last_heartbeat_at = datetime.utcnow()
        db.commit()

    log_audit_event(
        db, action="DEVICE_ENROLLED", actor_id=device.id, actor_type="device_agent",
        resource_type="device", resource_id=device.id, ip_address=client_ip,
        details={"hostname": reg_req.hostname, "os": reg_req.os_type}
    )

    return {"status": "enrolled", "device_id": device.id}

@router.post("/heartbeat")
def device_heartbeat(
    hb_req: DeviceHeartbeatRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    device = db.query(Device).filter(Device.device_identifier == hb_req.device_identifier).first()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not enrolled")

    device.is_online = True
    device.last_heartbeat_at = datetime.utcnow()
    device.agent_version = hb_req.agent_version
    device.ip_address = hb_req.ip_address or client_ip
    if hb_req.os_version:
        device.os_version = hb_req.os_version
    db.commit()

    return {"status": "acknowledged", "server_time": datetime.utcnow().isoformat()}

