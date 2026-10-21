-- =============================================================================
-- SECURE REMOTE DEVICE ACCESS - Seed Data
-- =============================================================================

-- Default Super Administrator (Password: Admin@Secure2026!)
INSERT INTO administrators (
    id, email, password_hash, full_name, role, mfa_secret, mfa_enabled, is_active
) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin@support.local',
    '$2b$12$I7UIEQ7/X6/riCpYKUHSwOjABHCkdFAFcG0vckPnLHqjpOvzRZ62G',
    'Primary System Administrator',
    'superadmin',
    'JBSWY3DPEHPK3PXP', -- Base32 Secret for TOTP
    FALSE,
    TRUE
) ON CONFLICT (email) DO NOTHING;

-- Standard Support Engineer
INSERT INTO administrators (
    id, email, password_hash, full_name, role, mfa_secret, mfa_enabled, is_active
) VALUES (
    '00000000-0000-0000-0000-000000000002',
    'tech@support.local',
    '$2b$12$I7UIEQ7/X6/riCpYKUHSwOjABHCkdFAFcG0vckPnLHqjpOvzRZ62G',
    'Technical Support Lead',
    'support_engineer',
    'JBSWY3DPEHPK3PXP',
    FALSE,
    TRUE
) ON CONFLICT (email) DO NOTHING;

-- Default Security Policies
INSERT INTO security_policies (policy_key, policy_value, description) VALUES
(
    'session_timeouts',
    '{"invitation_ttl_minutes": 15, "max_session_duration_minutes": 120, "inactivity_timeout_minutes": 15}',
    'Global session lifetime limits and idle disconnect rules'
),
(
    'privacy_controls',
    '{"allow_video_recording": false, "require_explicit_consent_screen": true, "show_floating_indicator": true, "allow_remote_input": false}',
    'Mandatory user privacy disclosures, explicit consent toggles, and zero-recording enforcement'
),
(
    'turn_configuration',
    '{"turn_server": "turn.support.local:3478", "turn_secret_configured": true, "ephemeral_credential_ttl_seconds": 3600}',
    'NAT traversal and Coturn relay server configuration parameters'
),
(
    'rate_limits',
    '{"max_login_attempts": 5, "lockout_minutes": 15, "invitations_per_hour": 30}',
    'Rate limiting controls for brute-force prevention and invitation flooding'
)
ON CONFLICT (policy_key) DO NOTHING;

-- Sample Enrolled Devices for Testing
INSERT INTO devices (
    id, device_identifier, hostname, os_type, os_version, ip_address, is_managed, is_online, last_heartbeat_at
) VALUES 
(
    '11111111-1111-1111-1111-111111111111',
    'CORP-WIN-08492',
    'Finance-Laptop-01',
    'windows',
    'Windows 11 Pro 23H2',
    '192.168.1.120',
    TRUE,
    TRUE,
    CURRENT_TIMESTAMP
),
(
    '22222222-2222-2222-2222-222222222222',
    'CORP-MAC-19381',
    'Engineering-MacBook-Pro',
    'macos',
    'macOS 14.6 Sonoma',
    '192.168.1.145',
    TRUE,
    FALSE,
    CURRENT_TIMESTAMP - INTERVAL '2 hours'
),
(
    '33333333-3333-3333-3333-333333333333',
    'CORP-AND-74921',
    'Field-Pixel8-Pro',
    'android',
    'Android 14 (Enterprise Managed)',
    '10.20.4.88',
    TRUE,
    TRUE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (device_identifier) DO NOTHING;

