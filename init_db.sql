-- Rimuru Opportunities Database Schema
-- Stores all discovered opportunities, approvals, and claims

CREATE TABLE IF NOT EXISTS opportunities (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    source VARCHAR(255) NOT NULL,
    estimated_value_usd DECIMAL(15, 2),
    total_supply VARCHAR(255),
    claiming_deadline TIMESTAMP,
    requirement TEXT,
    effort_level VARCHAR(50),
    estimated_roi DECIMAL(10, 4),
    blockchain VARCHAR(100),
    contract_address VARCHAR(255),
    url TEXT,
    data JSONB,
    discovered_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_source (source),
    INDEX idx_blockchain (blockchain),
    INDEX idx_discovered (discovered_at)
);

CREATE TABLE IF NOT EXISTS opportunity_approvals (
    id SERIAL PRIMARY KEY,
    opportunity_id VARCHAR(255) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    notes TEXT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
    INDEX idx_opportunity (opportunity_id),
    INDEX idx_status (status),
    INDEX idx_operator (operator)
);

CREATE TABLE IF NOT EXISTS opportunity_claims (
    id SERIAL PRIMARY KEY,
    opportunity_id VARCHAR(255) NOT NULL,
    claimed_by VARCHAR(100) NOT NULL,
    claimed_at TIMESTAMP NOT NULL,
    status VARCHAR(50),
    claim_notes TEXT,
    tx_hash VARCHAR(255),
    amount_received DECIMAL(20, 8),
    value_usd DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
    INDEX idx_opportunity (opportunity_id),
    INDEX idx_claimed_by (claimed_by),
    INDEX idx_status (status)
);

CREATE TABLE IF NOT EXISTS project_data (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL UNIQUE,
    project_path VARCHAR(500),
    crypto_assets JSONB,
    exchanges JSONB,
    api_keys_count INT DEFAULT 0,
    wallet_addresses JSONB,
    trading_strategies JSONB,
    defi_protocols JSONB,
    networks_used JSONB,
    total_files_scanned INT,
    findings JSONB,
    scanned_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_project_name (project_name),
    INDEX idx_scanned_at (scanned_at)
);

CREATE TABLE IF NOT EXISTS wallet_addresses (
    id SERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL UNIQUE,
    blockchain VARCHAR(100),
    source_project VARCHAR(255),
    first_found TIMESTAMP,
    last_found TIMESTAMP,
    balance DECIMAL(30, 8),
    balance_usd DECIMAL(15, 2),
    status VARCHAR(50),
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_address (address),
    INDEX idx_blockchain (blockchain),
    INDEX idx_source_project (source_project)
);

CREATE TABLE IF NOT EXISTS opportunities_completed (
    id SERIAL PRIMARY KEY,
    opportunity_id VARCHAR(255) NOT NULL,
    operator VARCHAR(100) NOT NULL,
    total_value_usd DECIMAL(15, 2),
    claim_count INT,
    completion_percentage DECIMAL(5, 2),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE,
    INDEX idx_opportunity (opportunity_id),
    INDEX idx_operator (operator),
    INDEX idx_completed (completed_at)
);

CREATE TABLE IF NOT EXISTS scan_history (
    id SERIAL PRIMARY KEY,
    scan_type VARCHAR(50) NOT NULL,
    source VARCHAR(255),
    opportunities_found INT,
    scan_duration_seconds DECIMAL(10, 2),
    status VARCHAR(50),
    error_message TEXT,
    scanned_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scan_type (scan_type),
    INDEX idx_source (source),
    INDEX idx_scanned_at (scanned_at)
);

-- Create indexes for better query performance
CREATE INDEX idx_opportunities_status 
ON opportunities (type, estimated_value_usd DESC);

CREATE INDEX idx_pending_approvals 
ON opportunity_approvals (status) 
WHERE status = 'pending';

CREATE INDEX idx_wallets_by_blockchain 
ON wallet_addresses (blockchain, address);

-- Insert initial data
INSERT INTO scan_history (scan_type, source, opportunities_found, status, scanned_at)
VALUES ('initial_setup', 'system', 0, 'completed', NOW())
ON CONFLICT DO NOTHING;
