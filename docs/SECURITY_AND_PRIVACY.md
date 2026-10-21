# Security Architecture, Cryptography & Privacy Compliance

## 1. Compliance & Security Verification Checklist

This platform has been architected to adhere to enterprise security standards including **SOC 2 Type II**, **ISO/IEC 27001**, **GDPR**, and **HIPAA**.

### Access Control & Authentication
- [x] **Multi-Factor Authentication (MFA):** TOTP (RFC 6238) enforced for all administrator logins.
- [x] **Brute-Force Lockout:** Automatic IP and account rate-limiting (5 consecutive failures = 15-minute lockout).
- [x] **Role-Based Access Control (RBAC):** Distinct roles: `superadmin`, `support_engineer`, and `auditor`.
- [x] **Least Privilege:** Support engineers can only view authorized screens; they cannot alter global privacy or system policies.

### Cryptographic Standards
- [x] **In-Transit Encryption:** TLS 1.3 enforced for all HTTPS and WebSocket (WSS) communication.
- [x] **Media Encryption:** Mandatory WebRTC **DTLS-SRTP** utilizing AES-128-GCM or AES-256-GCM cipher suites.
- [x] **Password Storage:** Salted and hashed using `bcrypt` (work factor 12).
- [x] **Access Token Generation:** 256 bits of cryptographic entropy generated via CSPRNG (`secrets.token_urlsafe(32)`).
- [x] **Token Storage Security:** Raw invitation tokens are **never** stored in plaintext. The database retains only irreversible SHA-256 digests (`token_hash`).
- [x] **TURN Server Authentication:** Ephemeral credentials generated using HMAC-SHA1 with unix timestamps (RFC 5766).

### Privacy & Transparency Controls
- [x] **Zero Persistent Recording by Default:** Screen frames are never written to disk or recorded unless an explicit company policy and secondary dual-party consent authorization are recorded.
- [x] **Explicit Purpose Declaration:** Administrators must submit a mandatory session justification (e.g., ticket number or diagnostic rationale) prior to link generation.
- [x] **Transparent Notification Banner:** Persistent, floating red badge displayed on the client display throughout active sharing.
- [x] **Instant Unilateral Revocation:** The end-user can click "Stop Sharing" at any time, immediately tearing down media pipelines and invalidating the token.
- [x] **Microphone & Camera Isolation:** WebRTC constraints explicitly set `{ audio: false }` and `Permissions-Policy` header blocks camera/mic activation.

---

## 2. Privacy & Regulatory Compliance

### 2.1. GDPR (EU General Data Protection Regulation)
* **Lawful Basis (Article 6(1)(a) & 6(1)(f)):** Processing is conducted based on explicit, informed consent given by the data subject at the moment of authorization, and legitimate interest for maintaining enterprise IT security.
* **Right to Withdraw Consent (Article 7(3)):** The client portal features an immediate "Disconnect Support Session" button. Termination immediately destroys the session key and halts data transmission.
* **Data Minimization (Article 5(1)(c)):** Only real-time visual frames required for immediate troubleshooting are transmitted. Frames pass ephemerally through RAM; zero visual media is stored in database tables or object storage.

### 2.2. HIPAA (Health Insurance Portability and Accountability Act)
* **Technical Safeguards (§ 164.312):**
  - **Transmission Security:** End-to-end DTLS-SRTP encryption ensures that Protected Health Information (PHI) displayed on-screen cannot be intercepted in transit.
  - **Audit Controls:** Immutable database records document every session initiation, duration, technician identity, and client IP address.

---

## 3. Web Application Security Hardening

### 3.1. Content Security Policy (CSP)
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' wss: ws:; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none';
```

### 3.2. Mandatory HTTP Security Headers
```http
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Permissions-Policy: display-capture=(self), camera=(), microphone=(), geolocation=()
```

---

## 4. Incident Response & Tamper Detection

1. **Compromised Token Detection:** If an invitation token is attempted after its expiration or after its single use has been consumed, the event is immediately logged as an `INVITATION_REPLAY_ATTEMPT` with client IP and User-Agent.
2. **Audit Ledger Immutability:** The PostgreSQL `audit_logs` table employs database rules that disallow `UPDATE` and `DELETE` operations, even by application database users:
   ```sql
   CREATE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
   CREATE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
   ```
3. **Emergency Revocation:** Administrators can revoke all outstanding invitation links globally or terminate an active session with a single click in the dashboard.

