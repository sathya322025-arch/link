-- =============================================================================
-- SECURE REMOTE DEVICE ACCESS & LIVE SCREEN MONITORING SYSTEM
-- PostgreSQL Database Schema (schema.sql)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enum Types
DO $$ BEGIN
    CREATE TYPE admin_role AS ENUM ('superadmin', 'support_engineer', 'auditor');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE os_family AS ENUM ('windows', 'macos', 'linux', 'android', 'ios', 'browser_generic');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE session_status AS ENUM ('requested', 'connecting', 'active', 'paused', 'ended', 'rejected', 'expired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE enrollment_status AS ENUM ('pending', 'active', 'suspended', 'revoked');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1. Administrators Table
CREATE TABLE IF NOT EXISTS administrators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role admin_role NOT NULL DEFAULT 'support_engineer',
    mfa_secret VARCHAR(64),
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    failed_login_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. End Users Table (Employees / Customers receiving support)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    department VARCHAR(100),
    phone VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Devices Table (Company-managed and recognized client devices)
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_identifier VARCHAR(128) UNIQUE NOT NULL, -- Hardware UUID or signed machine ID
    hostname VARCHAR(255) NOT NULL,
    os_type os_family NOT NULL,
    os_version VARCHAR(100),
    ip_address INET,
    mac_address VARCHAR(32),
    agent_version VARCHAR(50),
    is_managed BOOLEAN NOT NULL DEFAULT FALSE,
    is_online BOOLEAN NOT NULL DEFAULT FALSE,
    last_heartbeat_at TIMESTAMPTZ,
    registered_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Device Enrollments Table (Cryptographic provisioning records)
CREATE TABLE IF NOT EXISTS device_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    enrollment_token_hash VARCHAR(128) NOT NULL,
    enrolled_by_admin_id UUID REFERENCES administrators(id),
    policy_profile VARCHAR(100) NOT NULL DEFAULT 'standard_support',
    certificate_fingerprint VARCHAR(128),
    status enrollment_status NOT NULL DEFAULT 'active',
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    revoked_by_admin_id UUID REFERENCES administrators(id),
    revocation_reason TEXT
);

-- 5. Access Invitations Table (Short-lived single-use or scoped tokens)
CREATE TABLE IF NOT EXISTS access_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(128) UNIQUE NOT NULL, -- SHA-256 hash of single-use URL token
    token_hint VARCHAR(8) NOT NULL, -- Last 4-6 chars of token for admin reference
    target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    target_device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    created_by_admin_id UUID NOT NULL REFERENCES administrators(id),
    session_purpose VARCHAR(255) NOT NULL,
    permitted_actions JSONB NOT NULL DEFAULT '["screen_view", "live_pointer", "chat"]',
    expires_at TIMESTAMPTZ NOT NULL,
    max_uses INT NOT NULL DEFAULT 1,
    current_uses INT NOT NULL DEFAULT 0,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Remote Sessions Table (Active and Historical Screen-Sharing Sessions)
CREATE TABLE IF NOT EXISTS remote_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_code VARCHAR(32) UNIQUE NOT NULL,
    invitation_id UUID REFERENCES access_invitations(id) ON DELETE SET NULL,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    admin_id UUID NOT NULL REFERENCES administrators(id),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status session_status NOT NULL DEFAULT 'requested',
    started_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT DEFAULT 0,
    termination_reason VARCHAR(100),
    terminated_by VARCHAR(50), -- 'admin', 'user', 'timeout', 'network_disconnect'
    webrtc_connection_details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Authorization Records Table (User Consent Evidence and Privacy Disclosures)
CREATE TABLE IF NOT EXISTS authorization_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invitation_id UUID REFERENCES access_invitations(id) ON DELETE CASCADE,
    session_id UUID REFERENCES remote_sessions(id) ON DELETE CASCADE,
    user_consent_given BOOLEAN NOT NULL,
    consent_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    client_ip INET,
    user_agent TEXT,
    screen_sharing_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    permissions_granted JSONB NOT NULL,
    signature_digest VARCHAR(128),
    consent_notice_text TEXT NOT NULL
);

-- 8. Session Events Table (Real-time telemetry and timeline tracking)
CREATE TABLE IF NOT EXISTS session_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES remote_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'ice_connected', 'screen_share_started', 'paused', 'resumed', 'pointer_move', 'chat_message', 'terminated'
    actor VARCHAR(50) NOT NULL, -- 'admin', 'user', 'system'
    payload JSONB NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. Audit Logs Table (Append-Only Immutable Compliance Ledger)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID,
    actor_type VARCHAR(50) NOT NULL, -- 'admin', 'user', 'device_agent', 'system'
    action VARCHAR(100) NOT NULL, -- 'LOGIN_SUCCESS', 'INVITATION_CREATED', 'SESSION_AUTHORIZED', 'SESSION_TERMINATED', etc.
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Immutability Rule for Audit Logs: Disallow UPDATE and DELETE
CREATE OR REPLACE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE OR REPLACE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

-- 10. Security Policies Table (Global security & authorization controls)
CREATE TABLE IF NOT EXISTS security_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_key VARCHAR(100) UNIQUE NOT NULL,
    policy_value JSONB NOT NULL,
    description TEXT,
    updated_by_admin_id UUID REFERENCES administrators(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for High Performance and Efficient Lookup
CREATE INDEX IF NOT EXISTS idx_administrators_email ON administrators(email);
CREATE INDEX IF NOT EXISTS idx_devices_identifier ON devices(device_identifier);
CREATE INDEX IF NOT EXISTS idx_devices_online ON devices(is_online);
CREATE INDEX IF NOT EXISTS idx_invitations_token_hash ON access_invitations(token_hash);
CREATE INDEX IF NOT EXISTS idx_invitations_expires ON access_invitations(expires_at) WHERE is_revoked = FALSE;
CREATE INDEX IF NOT EXISTS idx_remote_sessions_status ON remote_sessions(status);
CREATE INDEX IF NOT EXISTS idx_remote_sessions_admin ON remote_sessions(admin_id);
CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

