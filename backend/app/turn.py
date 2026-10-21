import time
import hmac
import hashlib
import base64
from typing import List, Dict, Any
from app.config import settings

def get_ice_servers(username_prefix: str = "remote_session") -> List[Dict[str, Any]]:
    """
    Generates standard WebRTC ICE server configurations.
    If a TURN server and secret are configured, generates ephemeral RFC 5766 credentials.
    Otherwise falls back to public STUN for development/NAT testing.
    """
    ice_servers = [
        {"urls": [settings.STUN_SERVER]}
    ]

    if settings.TURN_SERVER and settings.TURN_SECRET:
        timestamp = int(time.time()) + settings.TURN_CREDENTIAL_TTL_SECONDS
        username = f"{timestamp}:{username_prefix}"
        
        # Coturn HMAC-SHA1 digest of username using turn secret
        digester = hmac.new(
            settings.TURN_SECRET.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha1
        )
        password = base64.b64encode(digester.digest()).decode("utf-8")

        ice_servers.append({
            "urls": [f"turn:{settings.TURN_SERVER}"],
            "username": username,
            "credential": password
        })
        # Add secure TURN (TURNS) over TLS if port 5349 is available
        ice_servers.append({
            "urls": [f"turns:{settings.TURN_SERVER}?transport=tcp"],
            "username": username,
            "credential": password
        })

    return ice_servers

