
-- Datenbankentwurf
CREATE TABLE drugs (
    stitch_id TEXT PRIMARY KEY,
    common_name TEXT
);

CREATE TABLE side_effects (
    se_code TEXT PRIMARY KEY,
    side_effect_name TEXT
);

-- Verbindungstabelle für Medikament -> Nebenwirkung
CREATE TABLE drug_side_effects (
    stitch_id TEXT REFERENCES drugs(stitch_id),
    se_code TEXT REFERENCES side_effects(se_code),
    is_combo BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (stitch_id, se_code)
);

-- Drug-Target Interaktionen
CREATE TABLE drug_targets (
    stitch_id TEXT REFERENCES drugs(stitch_id),
    protein_id TEXT,
    PRIMARY KEY (stitch_id, protein_id)
);

-- User Reports
CREATE TABLE user_reports (
    id SERIAL PRIMARY KEY,
    stitch_id TEXT REFERENCES drugs(stitch_id),
    reported_side_effect TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE MATERIALIZED VIEW mv_target_correlations AS
SELECT 
    pt.protein_id, 
    se.se_name, 
    COUNT(DISTINCT pt.drug_id) as drug_count
FROM drug_targets pt
JOIN drug_side_effects dse ON pt.drug_id = dse.drug_id
JOIN side_effects se ON dse.se_code = se.se_code
GROUP BY pt.protein_id, se.se_name
HAVING COUNT(DISTINCT pt.drug_id) > 1;

-- Damit die View auch einen Index hat:
CREATE INDEX idx_mv_protein_id ON mv_target_correlations(protein_id);


-- Indizes für die Verknüpfungen erstellen
CREATE INDEX IF NOT EXISTS idx_drug_targets_drug_id ON drug_targets(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_side_effects_drug_id ON drug_side_effects(drug_id);
CREATE INDEX IF NOT EXISTS idx_drug_side_effects_se_code ON drug_side_effects(se_code);
CREATE INDEX IF NOT EXISTS idx_drugs_stitch_id ON drugs(stitch_id);


VACUUM ANALYZE;

