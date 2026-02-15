-- MediMatch AI - Database Schema Definition
-- Part of the DBMS Project 2026
-- Targets: PostgreSQL 14+

-- 1. Create Main Catalog Tables
CREATE TABLE IF NOT EXISTS drugs (
    stitch_id VARCHAR(50) PRIMARY KEY,
    common_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS side_effects (
    se_code VARCHAR(50) PRIMARY KEY,
    se_name TEXT NOT NULL
);

-- 2. Create Relationship Tables (Mapping)
CREATE TABLE IF NOT EXISTS drug_side_effects (
    id SERIAL PRIMARY KEY,
    drug_id VARCHAR(50) REFERENCES drugs(stitch_id),
    se_code VARCHAR(50) REFERENCES side_effects(se_code),
    is_combo BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS drug_targets (
    id SERIAL PRIMARY KEY,
    drug_id VARCHAR(50) REFERENCES drugs(stitch_id),
    protein_id VARCHAR(100) NOT NULL
);

-- 3. Create Audit & Logging Table
CREATE TABLE IF NOT EXISTS user_logs (
    id SERIAL PRIMARY KEY,
    query_type VARCHAR(50) NOT NULL,
    input_text TEXT,
    result_data JSONB, -- JSONB for flexible metadata storage
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Performance Optimization (B-Tree Indexes)
-- Essential for handling >4 million records efficiently
CREATE INDEX IF NOT EXISTS idx_drug_se_drug_id ON drug_side_effects(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_se_code ON drug_side_effects(se_code);
CREATE INDEX IF NOT EXISTS idx_drug_targets_drug_id ON drug_targets(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_targets_protein_id ON drug_targets(protein_id);

-- 5. Scientific Analysis Module (Materialized View)
-- Precomputed aggregation of protein targets and their shared side effects
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_target_correlations AS
SELECT 
    dt.protein_id, 
    se.se_name, 
    COUNT(DISTINCT d.stitch_id) as drug_count
FROM drug_targets dt
JOIN drugs d ON dt.drug_id = d.stitch_id
JOIN drug_side_effects dse ON d.stitch_id = dse.drug_id
JOIN side_effects se ON dse.se_code = se.se_code
GROUP BY dt.protein_id, se.se_name
HAVING COUNT(DISTINCT d.stitch_id) > 1;

-- Refresh command (to be called after data import)
-- REFRESH MATERIALIZED VIEW mv_target_correlations;