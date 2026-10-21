/**
 * User Screen Sharing Portal Client Logic
 * Enforces explicit consent, displays transparency disclosures, and handles getDisplayMedia.
 */

let rtcManager = null;
let currentSessionCode = null;

async function initClientSession() {
  const pathParts = window.location.pathname.split("/");
  const token = pathParts[pathParts.length - 1];

  if (!token) {
    showError("Missing access token in invitation URL.");
    return;
  }

  try {
    const res = await fetch(`/api/v1/invitations/validate/${token}`);
    const data = await res.json();

    if (!data.valid) {
      showError(data.error || "Invalid or expired access link.");
      return;
    }

    document.getElementById("loadingCard").style.display = "none";
    document.getElementById("consentCard").style.display = "block";

    document.getElementById("adminNameDisplay").textContent = data.admin_name;
    document.getElementById("purposeDisplay").textContent = data.session_purpose;
    
    // Bind Start Sharing Button
    document.getElementById("btnAuthorize").addEventListener("click", () => startScreenShare(token, data));

  } catch (err) {
    showError("Network error connecting to support server.");
  }
}

function showError(msg) {
  document.getElementById("loadingCard").style.display = "none";
  document.getElementById("consentCard").style.display = "none";
  const errCard = document.getElementById("errorCard");
  errCard.style.display = "block";
  document.getElementById("errorMessage").textContent = msg;
}

async function startScreenShare(token, inviteData) {
  const btn = document.getElementById("btnAuthorize");
  btn.disabled = true;
  btn.textContent = "Requesting Browser Permissions...";

  try {
    // 1. Request user's display media via standard browser permission flow
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        cursor: "always",
        displaySurface: "monitor"
      },
      audio: false // No microphone or audio capture
    });

    btn.textContent = "Authorizing Session...";

    // 2. Transmit explicit consent record to server
    const authRes = await fetch("/api/v1/sessions/authorize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        invitation_token: token,
        user_consent_given: true,
        consent_notice_text: "User explicitly authorized live screen view via browser getDisplayMedia dialog.",
        permissions_granted: inviteData.permitted_actions,
        client_screen_info: {
          width: window.screen.width,
          height: window.screen.height,
          pixelRatio: window.devicePixelRatio
        }
      })
    });

    if (!authRes.ok) {
      const err = await authRes.json();
      throw new Error(err.detail || "Authorization rejected");
    }

    const authData = await authRes.json();
    currentSessionCode = authData.session_code;

    // 3. Setup WebRTC Peer Connection
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/signaling/${currentSessionCode}`;

    rtcManager = new WebRTCManager({
      role: "client",
      sessionCode: currentSessionCode,
      iceServers: authData.ice_servers,
      onConnectionStateChange: (state) => {
        console.log(`[Client] State changed: ${state}`);
        if (state === "ended" || state === "disconnected") {
          window.location.href = "/ended";
        }
      },
      onDataMessage: (data) => {
        if (data.type === "pointer") {
          updateLaserPointer(data);
        } else if (data.type === "chat") {
          addChatMessage("Technician", data.text);
        }
      }
    });

    await rtcManager.connectSignaling(wsUrl);
    await rtcManager.attachLocalScreen(stream);

    // 4. Handle browser native stop sharing button
    const screenTrack = stream.getVideoTracks()[0];
    screenTrack.onended = () => {
      terminateSession("Screen sharing stopped by user");
    };

    // 5. Update UI to Live Active View
    document.getElementById("consentCard").style.display = "none";
    document.getElementById("activeCard").style.display = "block";
    document.getElementById("floatingBanner").style.display = "flex";
    document.getElementById("sessionCodeDisplay").textContent = currentSessionCode;

  } catch (err) {
    console.error("Screen sharing error:", err);
    btn.disabled = false;
    btn.textContent = "Authorize and Share Screen";
    alert("Could not start screen sharing: " + err.message);
  }
}

function updateLaserPointer(data) {
  const pointerEl = document.getElementById("clientLaserPointer");
  if (!pointerEl) return;
  if (!data.active) {
    pointerEl.style.display = "none";
    return;
  }
  pointerEl.style.display = "block";
  pointerEl.style.left = `${data.x * 100}%`;
  pointerEl.style.top = `${data.y * 100}%`;
}

function terminateSession(reason) {
  if (rtcManager) {
    rtcManager.sendSignal({
      type: "session_terminate",
      reason: reason || "User clicked Stop Sharing"
    });
    rtcManager.close();
  }
  window.location.href = "/ended";
}

function sendClientChat() {
  const input = document.getElementById("clientChatInput");
  const text = input.value.trim();
  if (!text || !rtcManager) return;
  rtcManager.sendData({ type: "chat", text });
  addChatMessage("You", text);
  input.value = "";
}

function addChatMessage(sender, text) {
  const box = document.getElementById("clientChatBox");
  if (!box) return;
  const p = document.createElement("p");
  p.style.marginBottom = "0.4rem";
  p.innerHTML = `<strong>${sender}:</strong> <span>${escapeHtml(text)}</span>`;
  box.appendChild(p);
  box.scrollTop = box.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

window.addEventListener("DOMContentLoaded", initClientSession);

