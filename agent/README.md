# Enrolled Device Agent Deployment Guide

The `device_agent.py` runs on corporate-managed laptops and endpoints to provide continuous device identity verification, health telemetry, and authorized remote reconnection.

---

## 1. Enrollment Workflow

1. An administrator creates an Enrollment Token in the Administrator Portal (`/admin/devices`).
2. Run the enrollment command on the client machine:
   ```bash
   python device_agent.py --server https://support.yourcompany.com --enroll ENROLL-xxxxxxxxxxxxxxxx
   ```
3. The agent registers its hardware fingerprint, hostname, and OS with the server and stores credentials locally in `~/.remote_device_agent.json`.

---

## 2. Background Daemon Installation

### A. Windows Service (via NSSM or Windows Task Scheduler)
To run the agent automatically upon system boot:
```powershell
# Using NSSM (Non-Sucking Service Manager)
nssm install RemoteSupportAgent "C:\Python312\python.exe" "C:\Program Files\RemoteSupport\device_agent.py --run"
nssm set RemoteSupportAgent AppDirectory "C:\Program Files\RemoteSupport"
nssm start RemoteSupportAgent
```

### B. Linux (systemd service)
Create `/etc/systemd/system/remote-support-agent.service`:
```ini
[Unit]
Description=Secure Remote Support Enrolled Device Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/remote-support/device_agent.py --run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now remote-support-agent
```

### C. macOS (LaunchDaemon)
Create `/Library/LaunchDaemons/com.company.remotesupport.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.company.remotesupport</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Library/Application Support/RemoteSupport/device_agent.py</string>
        <string>--run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```
Load the daemon:
```bash
sudo launchctl load /Library/LaunchDaemons/com.company.remotesupport.plist
```

