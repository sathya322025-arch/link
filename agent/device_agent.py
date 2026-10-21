#!/usr/bin/env python3
"""
Secure Remote Support - Enrolled Device Management Agent
Cross-platform daemon for Windows, macOS, and Linux corporate endpoints.
Handles cryptographic device enrollment, periodic heartbeats, and authorized reconnects.
"""

import sys
import os
import json
import time
import socket
import platform
import argparse
import logging
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("device_agent")

CONFIG_FILE = os.path.expanduser("~/.remote_device_agent.json")
DEFAULT_SERVER = "http://localhost:8000"

def get_system_identifier():
    """Generates a stable hardware identifier based on platform characteristics."""
    node = platform.node()
    system = platform.system()
    machine = platform.machine()
    return f"{system}-{node}-{machine}".replace(" ", "_")

def enroll_device(server_url: str, enrollment_token: str):
    """Enrolls this machine using a cryptographically generated one-time token."""
    device_id = get_system_identifier()
    hostname = socket.gethostname()
    os_type = platform.system().lower()
    os_version = f"{platform.release()} ({platform.version()})"

    payload = {
        "hostname": hostname,
        "os_type": os_type,
        "os_version": os_version,
        "device_identifier": device_id,
        "enrollment_token": enrollment_token
    }

    url = f"{server_url.rstrip('/')}/api/v1/devices/register"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            logger.info("Successfully enrolled device: %s", data)
            
            # Save persistent credentials
            config = {
                "server_url": server_url,
                "device_identifier": device_id,
                "device_id": data.get("device_id"),
                "enrolled_at": time.time()
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Configuration saved to %s", CONFIG_FILE)
            return True
    except urllib.error.HTTPError as e:
        logger.error("Enrollment failed (HTTP %d): %s", e.code, e.read().decode())
        return False
    except Exception as e:
        logger.error("Enrollment error: %s", e)
        return False

def send_heartbeat(server_url: str, device_identifier: str):
    """Reports device health and online availability."""
    url = f"{server_url.rstrip('/')}/api/v1/devices/heartbeat"
    payload = {
        "device_identifier": device_identifier,
        "agent_version": "1.0.0",
        "os_version": f"{platform.system()} {platform.release()}"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        logger.warning("Heartbeat failure: %s", e)
        return False

def run_agent():
    """Main agent loop: runs continuously sending heartbeats."""
    if not os.path.exists(CONFIG_FILE):
        logger.error("Agent is not enrolled. Run with: --enroll <token> --server <url>")
        sys.exit(1)

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    server_url = config.get("server_url", DEFAULT_SERVER)
    device_id = config.get("device_identifier")

    logger.info("Starting Remote Support Agent for %s", device_id)
    logger.info("Connecting to server: %s", server_url)

    while True:
        success = send_heartbeat(server_url, device_id)
        if success:
            logger.debug("Heartbeat acknowledged")
        time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="Secure Remote Support Native Agent")
    parser.add_argument("--enroll", help="Enroll device with one-time token")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Server URL (default: http://localhost:8000)")
    parser.add_argument("--run", action="store_true", help="Run heartbeat daemon")

    args = parser.parse_args()

    if args.enroll:
        if enroll_device(args.server, args.enroll):
            print("\nDevice successfully enrolled. You can now start the daemon with: --run")
    elif args.run:
        run_agent()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

