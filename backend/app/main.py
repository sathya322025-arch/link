import os
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Administrator, SecurityPolicy
from app.security import get_password_hash
from app.signaling import signaling_manager
from app.routers import auth, invitations, sessions, devices, audit_logs, policies, health

# Initialize tables
Base.metadata.create_all(bind=engine)

def seed_initial_data():
    db: Session = SessionLocal()
    try:
        # Check if default admin exists
        admin = db.query(Administrator).filter(Administrator.email == "admin@support.local").first()
        if not admin:
            admin = Administrator(
                email="admin@support.local",
                password_hash=get_password_hash("Admin@Secure2026!"),
                full_name="Primary System Administrator",
                role="superadmin",
                mfa_secret="JBSWY3DPEHPK3PXP",
                mfa_enabled=False,
                is_active=True
            )
            db.add(admin)

        # Check default policies
        policy = db.query(SecurityPolicy).filter(SecurityPolicy.policy_key == "session_timeouts").first()
        if not policy:
            policies_to_seed = [
                SecurityPolicy(
                    policy_key="session_timeouts",
                    policy_value={"invitation_ttl_minutes": 15, "max_session_duration_minutes": 120, "inactivity_timeout_minutes": 15},
                    description="Session lifetime and idle limits"
                ),
                SecurityPolicy(
                    policy_key="privacy_controls",
                    policy_value={"allow_video_recording": False, "require_explicit_consent_screen": True, "show_floating_indicator": True, "allow_remote_input": False},
                    description="User privacy disclosures and recording policies"
                ),
                SecurityPolicy(
                    policy_key="turn_configuration",
                    policy_value={"turn_server": "turn.support.local:3478", "turn_secret_configured": True},
                    description="NAT traversal and Turn server settings"
                )
            ]
            for p in policies_to_seed:
                db.add(p)
        db.commit()
    finally:
        db.close()

seed_initial_data()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Enterprise-grade secure remote support and real-time screen monitoring architecture"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "display-capture=(self)"
    return response

# API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(invitations.router, prefix=settings.API_V1_STR)
app.include_router(sessions.router, prefix=settings.API_V1_STR)
app.include_router(devices.router, prefix=settings.API_V1_STR)
app.include_router(audit_logs.router, prefix=settings.API_V1_STR)
app.include_router(policies.router, prefix=settings.API_V1_STR)
app.include_router(health.router, prefix=settings.API_V1_STR)

# Locate Frontend Assets
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend" / "public"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# WebSocket Signaling Endpoint
@app.websocket("/ws/signaling/{session_code}")
async def websocket_signaling_endpoint(websocket: WebSocket, session_code: str):
    role = websocket.query_params.get("role", "client")
    await signaling_manager.connect(websocket, session_code, role)
    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            await signaling_manager.handle_message(session_code, role, data)
    except WebSocketDisconnect:
        signaling_manager.disconnect(session_code, role)
        # Inform peer of unexpected network disconnect
        await signaling_manager.broadcast_room(session_code, {
            "type": "peer_disconnected",
            "role": role
        })
    except Exception as e:
        signaling_manager.disconnect(session_code, role)

# Static and HTML Page Routes
@app.get("/")
def index_redirect():
    return RedirectResponse(url="/admin")

@app.get("/admin")
def serve_admin():
    return FileResponse(FRONTEND_DIR / "admin" / "index.html")

@app.get("/admin/login")
def serve_admin_login():
    return FileResponse(FRONTEND_DIR / "admin" / "login.html")

@app.get("/admin/console")
def serve_admin_console():
    return FileResponse(FRONTEND_DIR / "admin" / "console.html")

@app.get("/admin/devices")
def serve_admin_devices():
    return FileResponse(FRONTEND_DIR / "admin" / "devices.html")

@app.get("/admin/audit")
def serve_admin_audit():
    return FileResponse(FRONTEND_DIR / "admin" / "audit.html")

@app.get("/admin/settings")
def serve_admin_settings():
    return FileResponse(FRONTEND_DIR / "admin" / "settings.html")

@app.get("/join/{raw_token}")
def serve_client_join(raw_token: str):
    return FileResponse(FRONTEND_DIR / "client" / "session.html")

@app.get("/ended")
def serve_client_ended():
    return FileResponse(FRONTEND_DIR / "client" / "ended.html")

