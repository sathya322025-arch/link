import psutil
from datetime import datetime
from fastapi import APIRouter
from app.config import settings
from app.signaling import signaling_manager

router = APIRouter(prefix="/health", tags=["System Health"])

@router.get("")
def health_check():
    cpu_percent = psutil.cpu_percent(interval=None) if hasattr(psutil, "cpu_percent") else 0.0
    mem = psutil.virtual_memory() if hasattr(psutil, "virtual_memory") else None
    mem_percent = mem.percent if mem else 0.0

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": datetime.utcnow().isoformat(),
        "active_signaling_rooms": len(signaling_manager.active_rooms),
        "stun_configured": bool(settings.STUN_SERVER),
        "turn_configured": bool(settings.TURN_SERVER and settings.TURN_SECRET),
        "telemetry": {
            "cpu_usage_pct": cpu_percent,
            "memory_usage_pct": mem_percent
        }
    }

