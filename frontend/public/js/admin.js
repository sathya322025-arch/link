/**
 * Administrator Dashboard Client Logic
 */

const API_BASE = "/api/v1";

function getAuthHeader() {
  const token = localStorage.getItem("admin_access_token");
  if (!token) {
    window.location.href = "/admin/login";
    return {};
  }
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  };
}

async function checkAuth() {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Unauthorized");
    const admin = await res.json();
    const adminNameEl = document.getElementById("adminName");
    if (adminNameEl) adminNameEl.textContent = `${admin.full_name} (${admin.role})`;
  } catch (err) {
    localStorage.removeItem("admin_access_token");
    window.location.href = "/admin/login";
  }
}

async function loadDashboardMetrics() {
  try {
    const [sessionsRes, devicesRes] = await Promise.all([
      fetch(`${API_BASE}/sessions/active`, { headers: getAuthHeader() }),
      fetch(`${API_BASE}/devices`, { headers: getAuthHeader() })
    ]);

    const sessions = await sessionsRes.json();
    const devices = await devicesRes.json();

    const activeSessionsEl = document.getElementById("metricActiveSessions");
    if (activeSessionsEl) activeSessionsEl.textContent = sessions.length;

    const managedDevicesEl = document.getElementById("metricManagedDevices");
    if (managedDevicesEl) managedDevicesEl.textContent = devices.length;

    const onlineDevicesEl = document.getElementById("metricOnlineDevices");
    if (onlineDevicesEl) {
      const onlineCount = devices.filter(d => d.is_online).length;
      onlineDevicesEl.textContent = onlineCount;
    }

    renderActiveSessions(sessions);
  } catch (err) {
    console.error("Error loading metrics:", err);
  }
}

function renderActiveSessions(sessions) {
  const tbody = document.getElementById("sessionsTableBody");
  if (!tbody) return;

  if (sessions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:2rem;">No active support sessions in progress.</td></tr>`;
    return;
  }

  tbody.innerHTML = sessions.map(s => `
    <tr>
      <td><strong>${s.session_code}</strong></td>
      <td>${s.user_name || "Guest User"}</td>
      <td>${s.device_name}</td>
      <td>
        <span class="badge badge-${s.status}">
          <span class="badge-pulse"></span>
          ${s.status.toUpperCase()}
        </span>
      </td>
      <td>${Math.floor(s.duration_seconds / 60)}m ${s.duration_seconds % 60}s</td>
      <td>
        <a href="/admin/console?code=${s.session_code}" class="btn btn-primary" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">
          Open Console
        </a>
      </td>
    </tr>
  `).join("");
}

// Generate Invitation Modal
function openInviteModal() {
  document.getElementById("inviteModal").style.display = "flex";
  document.getElementById("inviteResult").style.display = "none";
  document.getElementById("inviteForm").style.display = "block";
}

function closeInviteModal() {
  document.getElementById("inviteModal").style.display = "none";
}

async function submitInvite(event) {
  event.preventDefault();
  const purpose = document.getElementById("invitePurpose").value;
  const userEmail = document.getElementById("inviteEmail").value;
  const ttl = parseInt(document.getElementById("inviteTTL").value, 10);

  try {
    const res = await fetch(`${API_BASE}/invitations`, {
      method: "POST",
      headers: getAuthHeader(),
      body: JSON.stringify({
        session_purpose: purpose,
        target_user_email: userEmail || null,
        expires_in_minutes: ttl,
        permitted_actions: ["screen_view", "live_pointer", "chat"]
      })
    });

    if (!res.ok) throw new Error("Failed to create invitation");
    const data = await res.json();

    document.getElementById("inviteForm").style.display = "none";
    document.getElementById("inviteResult").style.display = "block";
    document.getElementById("generatedLink").value = data.access_url;
  } catch (err) {
    alert("Error generating invitation: " + err.message);
  }
}

function copyGeneratedLink() {
  const input = document.getElementById("generatedLink");
  input.select();
  navigator.clipboard.writeText(input.value);
  alert("Access link copied to clipboard!");
}

function logout() {
  localStorage.removeItem("admin_access_token");
  window.location.href = "/admin/login";
}

