# Operating System Feasibility, Security Sandboxes, and Architectural Limitations

## 1. Executive Summary & Reality Check

> [!CAUTION]
> **The Web Link Fallacy:** A web link opened in a standard mobile or desktop browser **cannot** grant unrestricted, silent, or persistent administrative access to a device. Operating system security boundaries, modern browser sandboxes, and platform permission models deliberately prevent remote code execution or unattended access via a simple URL. Any platform claiming that a user simply "clicks a link and gives full remote control without prompts or native software" is either misrepresenting reality or relying on unpatched zero-day vulnerabilities.

This document provides a technical analysis of what is possible, what is restricted, and what requires enterprise-enrolled native software across desktop and mobile platforms.

---

## 2. Comparison Matrix: Access Models

| Capability | Browser-Based Session (Link Only) | Ad-Hoc Native Agent (QuickSupport) | Enrolled Managed Device (MDM / Agent) |
| :--- | :--- | :--- | :--- |
| **Prerequisites** | Modern Web Browser | Download and run temporary `.exe` / `.pkg` | Pre-enrolled via MDM / GPO / Intune / Signed Agent |
| **User Interaction** | Must click link + grant browser permission | Must download, run, and approve OS UAC/TCC prompt | Configured in advance; optional one-click prompt |
| **Screen Viewing** | Full Screen, Tab, or Window (via `getDisplayMedia`) | Full Desktop Screen | Full Desktop Screen (Windows/macOS/Linux) |
| **Remote Mouse / Keyboard Control** | **Impossible** (outside browser canvas) | Possible with elevated OS privileges | Possible with elevated OS privileges |
| **Mobile Screen Sharing** | Android: Chrome prompt<br>iOS: Limited tab capture | Android: MediaProjection API<br>iOS: ReplayKit broadcast extension | Android: Knox / OEM signed<br>iOS: Screen broadcast only (no remote touch) |
| **Unattended Access** | **Impossible** | Impossible (requires user to run binary) | **Possible** on Windows/Linux; Limited on macOS 15 |
| **Hardware Sensor Access** | Camera/Mic blocked by security policy | Blocked by default | Configurable via enterprise policy |
| **Revocation** | Close browser tab | Terminate process | Centralized cloud revocation via admin dashboard |

---

## 3. Deep-Dive: Platform Feasibility & Restrictions

### 3.1. Browser-Based Remote Support (Link-Only)
* **API Used:** W3C Screen Capture API (`navigator.mediaDevices.getDisplayMedia`).
* **Technical Flow:**
  1. The user clicks a short-lived, single-use HTTPS link.
  2. The browser renders the web application and displays technician credentials and session purpose.
  3. The user clicks "Authorize and Share Screen".
  4. The operating system and browser present an unavoidable native picker: "Choose what to share: Entire Screen, Window, or Tab".
  5. Screen frames are encoded via VP8/VP9/H.264 and transmitted via WebRTC DTLS-SRTP.
* **Capabilities:**
  - Real-time live screen viewing at 30-60 FPS.
  - Interactive telestrator drawing and laser pointer overlaid on the shared stream.
  - Bidirectional text chat and session diagnostics.
* **Hard Limitations:**
  - **No OS Remote Control:** Browsers cannot inject mouse clicks, keypresses, or window management commands into the operating system desktop outside the web page.
  - **No Unattended Access:** The user must explicitly choose the screen and confirm every session.
  - **No Hardware Sensor Hijacking:** Cannot activate webcam or microphone without secondary, explicit browser permissions (which our secure architecture explicitly disables).

---

### 3.2. Mobile Devices (Android vs. iOS)

#### A. Android Architecture
* **Live Screen Sharing:**
  - *Browser:* Android Chrome supports `getDisplayMedia` on modern versions, triggering a system prompt: *"Start recording or casting with Chrome?"*.
  - *Native App / Agent:* Uses the Android `MediaProjection` API. Requires user confirmation on every launch unless enrolled as a Device Owner (Enterprise EMM/MDM).
* **Remote Control (Touch Injection):**
  - Standard consumer Android prohibits apps from injecting touch events into other apps for security and anti-malware reasons.
  - **Permitted Methods:**
    1. **Accessibility Services (`AccessibilityService`):** Can perform gestures (`dispatchGesture`) and click buttons. Requires the user to manually enable the service in Android Settings -> Accessibility.
    2. **OEM Signed Partnerships (Samsung Knox, Zebra, Honeywell):** Pre-installed or platform-signed system apps can obtain `INJECT_EVENTS` system permissions without user prompts on enterprise fleets.
    3. **Android Enterprise (Device Owner / Work Profile):** Enterprise Mobility Management (EMM) enables remote reboot, app deployment, and device lock, but screen streaming still alerts the user.

#### B. iOS Architecture (Apple Sandboxing)
* **Live Screen Sharing:**
  - *Browser:* iOS Safari does not support general desktop/device screen capture via `getDisplayMedia` due to Apple's strict privacy sandboxing.
  - *Native App / Agent:* Must implement a **ReplayKit Broadcast Extension** (`RPBroadcastSampleHandler`).
  - *User Flow:* The user must open Control Center, long-press the Screen Recording icon, select the Support Broadcast extension, and tap "Start Broadcast". A prominent red status bar pill is displayed at all times.
* **Remote Control (Touch Injection):**
  - **Technically Impossible on standard iOS:** Apple strictly forbids third-party apps from synthesizing touch events or controlling the iOS UI outside their own sandbox. Any app attempting this would be rejected from the App Store and would violate Apple's developer agreement.
  - **Apple MDM Capabilities:** Apple Enterprise MDM allows remote wiping, passcode reset, configuration profile push, and lost mode, but Apple does not provide APIs for unattended remote desktop control of iPhones or iPads.

---

### 3.3. Desktop Operating Systems (Unattended & Managed Access)

#### A. Windows (10 / 11)
* **Architecture:**
  - Native service running as `NT AUTHORITY\SYSTEM` (session 0).
  - A helper process is spawned in the active user console session (Session 1+) using `CreateProcessAsUser` with `uiAccess=true` to capture the desktop via Desktop Duplication API (DXGI) or Windows Graphics Capture API.
* **Unattended Access:** Fully supported if installed as a Windows Service with appropriate administrative rights.
* **User Consent:** Can be configured to prompt the local logged-in user or allow immediate connection if the machine is locked / unattended.

#### B. macOS (Sonoma, Sequoia 15+)
* **Apple TCC (Transparency, Consent, and Control):**
  - Requires **Screen Recording** permission and **Accessibility** permission in System Settings.
  - In macOS 15 Sequoia, Apple introduced recurring monthly prompts reminding users that third-party applications have screen recording privileges.
* **Enterprise MDM Provisioning:**
  - MDM (Jamf, Kandji, Intune) can push Privacy Preferences Policy Control (PPPC / TCC) profiles to pre-approve Accessibility and remote input.
  - However, Apple explicitly prohibits MDM profiles from pre-approving Screen Recording without at least one user authorization.

#### C. Linux (X11 vs. Wayland)
* **X11:** Trivial to capture screen (`XShmGetImage` or X11 grab) and inject events (`XTestFakeKeyEvent`).
* **Wayland (Modern Ubuntu, Fedora, RHEL):** Wayland isolates display clients from each other. Screen capture must go through the **XDG Desktop Portal** (`org.freedesktop.portal.ScreenCast`) via PipeWire and WebRTC, which presents a permission dialog to the user.

