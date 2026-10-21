# System Architecture & Technical Specification

## 1. High-Level Architecture Overview

The Secure Remote Device Access Platform connects client devices to an administrator's operations dashboard via authenticated WebRTC peer-to-peer data and media pipelines, coordinated by a hardened backend signaling service.

```mermaid
flowchart TD
    subgraph ClientEndpoint["Client Device (Target)"]
        Browser["Modern Web Browser (getDisplayMedia)"]
        Agent["Enrolled Native Agent (Background Daemon)"]
    end

    subgraph Infrastructure["Enterprise Cloud Infrastructure"]
        Nginx["Nginx Reverse Proxy (TLS 1.3 Termination & WSS)"]
        API["FastAPI Core & WebSockets Signaling Room Manager"]
        Postgres[(PostgreSQL 16 Database with Immutable Auditing)]
        Coturn["Coturn STUN / TURN Server (RFC 5766 Relay)"]
    end

    subgraph AdminConsole["Administrator Console"]
        AdminUI["Admin Web Dashboard (React / Vanilla JS)"]
        WebRTCViewer["Live Screen Support Console (DTLS-SRTP Receiver)"]
    end

    Browser -- "1. Single-Use HTTPS Link" --> Nginx
    Agent -- "1b. mTLS / Provisioning Token" --> Nginx
    Nginx --> API
    API <--> Postgres
    API -- "Dynamic Ephemeral Credentials" --> Coturn

    AdminUI -- "2. Authenticate + MFA" --> Nginx
    Browser <-.->|"3. WebRTC DTLS-SRTP Media (Encrypted)"| Coturn
    WebRTCViewer <-.->|"4. WebRTC DTLS-SRTP Media (Encrypted)"| Coturn
    Browser <==>|"Direct P2P Media (if NAT allows)"| WebRTCViewer
```

---

## 2. Secure Access-Link Workflow (Sequence Diagram)

This sequence diagram illustrates the lifecycle of a single-use remote support session, enforcing explicit user consent, cryptographic token hashing, and immediate revocation upon session termination.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Support Administrator
    participant Dashboard as Admin Dashboard
    participant Server as Support API & Signaling
    participant DB as PostgreSQL Ledger
    actor User as Client User
    participant ClientBrowser as Client Browser

    Admin->>Dashboard: Requests single-use access link (Purpose, Expiration)
    Dashboard->>Server: POST /api/v1/invitations
    Server->>Server: Generates 32-byte secure token (T_raw) & SHA-256 (T_hash)
    Server->>DB: Store T_hash, purpose, expires_at, max_uses=1
    Server->>DB: Log INVITATION_CREATED in audit ledger
    Server-->>Dashboard: Returns https://support.company.com/join/T_raw
    Admin->>User: Transmits link via secure chat or email

    User->>ClientBrowser: Opens invitation link
    ClientBrowser->>Server: GET /api/v1/invitations/validate/T_raw
    Server->>DB: Verify SHA-256(T_raw), expiration, and revocation status
    Server-->>ClientBrowser: Returns Admin Name, Purpose, Permitted Scope

    ClientBrowser->>User: Displays technician identity, purpose & privacy guarantees
    User->>ClientBrowser: Clicks "Authorize and Share Screen"
    ClientBrowser->>ClientBrowser: Prompts native navigator.mediaDevices.getDisplayMedia()
    User->>ClientBrowser: Selects Screen/Window to share
    
    ClientBrowser->>Server: POST /api/v1/sessions/authorize (T_raw, consent_text, client_meta)
    Server->>DB: Mark invitation current_uses = 1 (Invalidate token)
    Server->>DB: Insert AuthorizationRecord & RemoteSession (Connecting)
    Server-->>ClientBrowser: Returns session_code & ephemeral TURN credentials

    ClientBrowser->>Server: Connect WebSocket /ws/signaling/{session_code}?role=client
    Dashboard->>Server: Connect WebSocket /ws/signaling/{session_code}?role=admin
    
    Note over ClientBrowser,Dashboard: WebRTC Negotiation: SDP Offer, Answer, ICE Candidates
    ClientBrowser->>Dashboard: WebRTC DTLS-SRTP Peer Connection Established
    ClientBrowser->>Dashboard: Live Video Stream (VP8/H.264) + DataChannel (Pointer/Chat)
    
    Note over ClientBrowser,Dashboard: Active Support Session: Live pointer, telestrator, chat
    
    alt User or Admin ends session
        User->>ClientBrowser: Clicks "Stop Sharing" (or Admin clicks "End Session")
        ClientBrowser->>Server: Sends session_terminate signal
        Server->>DB: Update RemoteSession status='ended', duration, reason
        Server->>DB: Append immutable audit record
        ClientBrowser->>ClientBrowser: Dismantles MediaStream tracks and closes PeerConnection
        ClientBrowser->>User: Redirects to Session Ended receipt
    end
```

---

## 3. Enrolled Device Reconnection Workflow

For enterprise-owned endpoints with the background management agent installed:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Support Administrator
    participant Dashboard as Admin Dashboard
    participant Server as Core Support Server
    participant DB as PostgreSQL Database
    participant Agent as Enrolled Device Agent (Laptop/Phone)

    Agent->>Server: Periodic heartbeat (POST /api/v1/devices/heartbeat)
    Server->>DB: Updates device online status and IP address
    
    Admin->>Dashboard: Selects enrolled device -> "Initiate Support Session"
    Dashboard->>Server: POST /api/v1/sessions/initiate-enrolled (device_id, purpose)
    Server->>Server: Validates admin permissions & enterprise policy
    Server->>DB: Creates RemoteSession with unique session_code
    
    alt Attended Policy (User at device)
        Server->>Agent: Sends Push / WebSocket connection request
        Agent->>Agent: Displays prompt on user desktop: "Admin X is requesting screen assistance"
        Agent->>Server: User confirms -> session token validated
    else Unattended Policy (Permitted server/kiosk access)
        Server->>Agent: Sends authorized connection token verified via device certificate
    end

    Agent->>Server: Connects WebRTC signaling with session_code
    Dashboard->>Server: Connects WebRTC signaling with session_code
    Agent->>Dashboard: Establishes DTLS-SRTP video stream
    Server->>DB: Logs SESSION_START in immutable audit trail
```

---

## 4. Threat Model & Mitigations (STRIDE Framework)

| STRIDE Category | Threat Description | Architectural Mitigation |
| :--- | :--- | :--- |
| **Spoofing** | Adversary attempts to impersonate an administrator or forge an invitation. | Mandatory MFA (TOTP) for admins; Single-use 256-bit entropy tokens; SHA-256 token hashing; TLS 1.3 certificate validation. |
| **Tampering** | Interception or modification of live screen video or chat in transit. | Mandatory WebRTC DTLS-SRTP encryption (AES-128/256-GCM); WebSocket TLS encryption; Strict CSP and HSTS headers. |
| **Repudiation** | An administrator claims they did not initiate a remote session or accessed unauthorized devices. | Append-only immutable `audit_logs` table protected with PostgreSQL database rules preventing UPDATE and DELETE; client IP, user-agent, and consent signatures recorded. |
| **Information Disclosure** | Leakage of access tokens from database dumps or URL referrer headers. | Single-use raw tokens are **never stored** in the database (only salted SHA-256 hashes are persisted); `Referrer-Policy: strict-origin-when-cross-origin`. |
| **Denial of Service** | Flooding login endpoints or TURN relay servers to exhaust bandwidth. | Nginx rate-limiting zones (`limit_req_zone`); RFC 5766 ephemeral HMAC TURN credentials prevent open relay abuse. |
| **Elevation of Privilege** | An attacker using a web link to gain shell execution or root access. | Zero native code execution from the browser sandbox; the link uses browser-native `getDisplayMedia` with no OS-level input injection capability. |

