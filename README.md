# Secure Remote Device Access & Live Screen Monitoring System

An enterprise-ready, privacy-centric remote device support and live screen monitoring platform architected around explicit user authorization, transparent indicators, and zero covert surveillance.

---

## 🌟 Key Architecture Highlights

- **Consent-First Browser Support:** Instant remote technical assistance via single-use, cryptographically generated access links utilizing W3C standard `getDisplayMedia`. No software installation required for guests.
- **Enterprise Managed Endpoint Support:** Persistent device enrollment, health telemetry, and authorized reconnects for corporate laptops and mobile devices via signed background agents.
- **Strict Privacy Guarantees:** Zero silent hardware activation (no webcams, no microphones). Prominent, persistent visual indicators during live sessions. Zero server-side video recordings by default.
- **High-Performance WebRTC Media:** Ultra-low-latency screen transmission via **DTLS-SRTP** encrypted WebRTC channels with automated **STUN/TURN (Coturn)** NAT traversal.
- **Cryptographic Audit Trail:** Immutable PostgreSQL event ledger recording every session initiation, technician credential, client IP, and explicit consent artifact.

---

## 📁 Repository Structure

```
C:\Users\MK\Documents\link\
├── README.md                      # Master system overview and quickstart
├── docker-compose.yml             # Production Docker stack (PostgreSQL, Coturn, FastAPI, Nginx)
├── Dockerfile                     # Multi-stage container definition
├── docs/                          # In-depth architectural & compliance specifications
│   ├── ARCHITECTURE.md            # Sequence diagrams, WebRTC signaling & threat model
│   ├── FEASIBILITY_AND_LIMITATIONS.md # OS sandboxes (Browser vs Native vs Mobile Android/iOS)
│   ├── SECURITY_AND_PRIVACY.md    # Cryptographic standards, GDPR/HIPAA & security checklist
│   ├── DEPLOYMENT_GUIDE.md        # Linux server setup, Coturn config & TLS reverse proxy
│   └── TESTING_PLAN.md            # Cross-platform testing matrix (Win, Mac, Android, iOS)
├── backend/                       # Core FastAPI & WebSockets Signaling Backend
│   ├── requirements.txt           # Python dependencies
│   ├── .env.example               # Environment variables template
│   └── app/
│       ├── main.py                # Application factory, security middleware, static routes
│       ├── config.py              # Pydantic environment settings
│       ├── database.py            # SQLAlchemy engine (SQLite dev fallback / PostgreSQL prod)
│       ├── models.py              # 10 core data models (Administrators, Sessions, Devices, etc.)
│       ├── schemas.py             # Pydantic request/response schemas
│       ├── security.py            # Bcrypt, JWT, TOTP MFA, and SHA-256 token hashing
│       ├── audit.py               # Structured audit event logger
│       ├── turn.py                # RFC 5766 REST API ephemeral TURN credentials generator
│       ├── signaling.py           # WebSocket room manager (SDP offer/answer, ICE candidates)
│       └── routers/               # Modular API endpoints (auth, invitations, sessions, etc.)
├── frontend/                      # Web Client & Admin Dashboard
│   └── public/
│       ├── css/app.css            # Responsive dark-mode styling and session badges
│       ├── js/
│       │   ├── admin.js           # Admin portal logic (session monitor, invitation creator)
│       │   ├── client.js          # User portal (explicit consent, getDisplayMedia capture)
│       │   ├── webrtc_helper.js   # Reusable WebRTC manager (RTCPeerConnection & DataChannel)
│       │   └── canvas_tools.js    # Telestrator pen drawing and virtual laser pointer
│       ├── admin/                 # Admin Dashboard, Console, Devices, Audit & Settings
│       └── client/                # Client invitation portal & session ended confirmation
├── database/                      # Production PostgreSQL assets
│   ├── schema.sql                 # Pure PostgreSQL DDL with immutability rules and indexes
│   └── seed.sql                   # Default superadmin and initial security policies
├── coturn/
│   └── turnserver.conf            # Hardened Coturn TURN/STUN configuration
├── nginx/
│   └── nginx.conf                 # Production reverse proxy with SSL, HSTS, CSP & rate-limiting
└── agent/                         # Enrolled device background agent
    ├── device_agent.py            # Cross-platform daemon for managed Windows, macOS, Linux
    └── README.md                  # Service installation (Windows Service, macOS plist, systemd)
```

---

## 🚀 Quickstart Guide (Local Development)

The backend is configured to support immediate zero-dependency local running (using embedded SQLite) or production PostgreSQL.

### 1. Run Backend Server
Open PowerShell or your command prompt:
```powershell
cd C:\Users\MK\Documents\link\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Access Portals
- **Administrator Dashboard:** Open `http://localhost:8000/admin`
  - **Email:** `admin@support.local`
  - **Password:** `Admin@Secure2026!`
- **Interactive API Documentation:** Open `http://localhost:8000/docs`

### 3. Generate a Test Support Session
1. Log into the Administrator Dashboard.
2. Click **"Generate Access Link"**.
3. Enter a session purpose (e.g., *"Diagnostic of Outlook sync issue"*) and click **Generate**.
4. Copy the single-use URL (e.g. `http://localhost:8000/join/xxxxxx`) and open it in a secondary browser window or incognito tab.
5. Review the transparent privacy disclosures and click **"Authorize and Share Screen"**.
6. Select your screen or window in the browser dialog.
7. Return to the Administrator Dashboard, click **"Open Console"**, and observe the live screen stream, interactive laser pointer, and bidirectional chat in real time!

---

## 🐳 Production Deployment (Docker Compose)

For production deployment with PostgreSQL, Coturn, and Nginx:
```bash
cd C:\Users\MK\Documents\link
docker compose up -d --build
```
Refer to [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for full server configuration, domain SSL certificate setup, and Coturn NAT traversal port mappings.

