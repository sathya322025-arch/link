# Comprehensive Cross-Platform Testing & Quality Assurance Plan

## 1. Test Matrix Overview

| Test Domain | Platforms Covered | Browsers / Run-times | Primary Verification Objectives |
| :--- | :--- | :--- | :--- |
| **Desktop Client** | Windows 10/11, macOS Sonoma/Sequoia, Ubuntu Linux | Google Chrome, MS Edge, Mozilla Firefox, Apple Safari | `getDisplayMedia` dialog, stream resolution, frame rate, floating banner indicator. |
| **Mobile Client** | Android 12, 13, 14, iOS 16, 17, 18 | Chrome Android, Mobile Safari | Mobile consent flow, portrait/landscape orientation change, touch events. |
| **Enrolled Agent** | Windows 11, macOS 14, Linux | Python 3.10+ Native Daemon | Registration handshake, token exchange, 30s heartbeat survival, auto-reconnect. |
| **NAT & Connectivity**| Direct LAN, Symmetric NAT, Corporate Proxy | WebRTC ICE Agent, Coturn | STUN direct P2P discovery, fallback to TURN UDP (port 3478), fallback to TURNS TCP (port 5349). |
| **Security & Pen-testing** | Web Application & WebSocket API | Burp Suite, OWASP ZAP, Postman | Single-use token exhaustion, token expiration replay, MFA bypass, SQL injection, CSP enforcement. |

---

## 2. Test Execution Procedures

### Test Case 1: Browser-Based Invitation Lifecycle
1. **Step:** Admin logs into `/admin/login` with MFA.
2. **Step:** Generates a 15-minute single-use link for target `user@test.local`.
3. **Step:** Opens the link in an Incognito browser window.
4. **Expected:**
   - Public page loads displaying technician identity, stated purpose, and privacy disclosures.
   - User clicks "Authorize and Share Screen".
   - Browser displays system screen picker.
   - User approves -> WebRTC negotiation completes within < 1.5 seconds.
   - Admin console shows live video feed with FPS > 25.
   - Floating banner appears on client with "Stop Sharing" button.
5. **Step:** User clicks "Stop Sharing".
6. **Expected:** Both ends immediately dismantle connection. User is redirected to `/ended`. Refreshing the original link returns "This single-use access link has already been used".

### Test Case 2: Network Traversal & TURN Relay
1. **Step:** Simulate a restrictive symmetric NAT environment by blocking direct UDP peer-to-peer traffic between client and admin.
2. **Step:** Inspect `chrome://webrtc-internals` during call negotiation.
3. **Expected:**
   - Candidate pair type transitions from `host` or `srflx` to `relay`.
   - Coturn receives relayed media over port 3478.
   - Video stream maintains steady throughput with 0% connection drop.

### Test Case 3: Replay & Fuzzing Security Validation
1. **Expired Token Replay:** Attempt to authorize a session with an expired timestamp. Must return HTTP 400 with detail "This support link has expired".
2. **Revocation Interruption:** Admin clicks "Revoke" on an unused invitation. Client attempting to open the link must receive HTTP 400 "This support link was revoked by an administrator".
3. **Database Audit Verification:**
   - Query `SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 5;`
   - Attempt an `UPDATE audit_logs SET action = 'ALTERED';`
   - Must fail or trigger zero affected rows due to the immutable rule.

