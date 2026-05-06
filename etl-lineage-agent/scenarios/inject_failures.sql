-- ============================================================
-- SCENARIO 1: Empty Target Table
-- Simulate: fact_claims load failed, table is empty for today
-- Agent should: trace lineage, find work layer has data, rerun load
-- ============================================================

-- Inject failure
DELETE FROM data_layer.fact_claims WHERE load_date = CURRENT_DATE;
INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, error_message, run_date)
VALUES ('load_fact_claims', 'data_layer', 'fact_claims', 'FAILED', 0, 'Connection timeout during merge operation', CURRENT_DATE);


-- ============================================================
-- SCENARIO 2: Duplicate Keys in Staging
-- Simulate: source sent duplicate claim records, merge will fail
-- Agent should: find duplicates, dedup staging, rerun merge
-- ============================================================

-- Inject duplicates (copy 50 random claims again with same claim_id)
INSERT INTO staging_layer.claims_staged (claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name, hash_key, is_valid, load_date)
SELECT claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name, hash_key, is_valid, CURRENT_DATE
FROM staging_layer.claims_staged
ORDER BY RANDOM() LIMIT 50;

INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, error_message, run_date)
VALUES ('load_fact_claims', 'data_layer', 'fact_claims', 'FAILED', 0, 'Duplicate key violation: claim_id already exists in target', CURRENT_DATE);


-- ============================================================
-- SCENARIO 3: Row Count Drop (Partial Source File)
-- Simulate: source only sent 200 records instead of usual 2000
-- Agent should: detect variance, flag partial load, alert
-- ============================================================

-- Clear today's source and add only 200 records
DELETE FROM source_layer.claims_raw WHERE load_date = CURRENT_DATE;
INSERT INTO source_layer.claims_raw (claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name, load_date)
SELECT
    2000 + s AS claim_id,
    1 + (random() * 799)::INT,
    1 + (random() * 499)::INT,
    CURRENT_DATE,
    50 + (random() * 5000)::INT,
    (ARRAY['ACCIDENT','HOSPITAL','CANCER'])[1 + (random()*2)::INT],
    'SUBMITTED',
    'ICD' || LPAD((random()*999)::INT::TEXT, 3, '0'),
    'Provider_' || (1 + (random()*99)::INT),
    CURRENT_DATE
FROM generate_series(1, 200) s;

-- Propagate partial data through pipeline
DELETE FROM staging_layer.claims_staged WHERE load_date = CURRENT_DATE;
INSERT INTO staging_layer.claims_staged (claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name, hash_key, is_valid, load_date)
SELECT claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name,
    MD5(claim_id::TEXT || COALESCE(status,'') || amount::TEXT), TRUE, CURRENT_DATE
FROM source_layer.claims_raw WHERE load_date = CURRENT_DATE;

INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, error_message, run_date)
VALUES ('load_claims_staged', 'staging_layer', 'claims_staged', 'SUCCESS', 200, NULL, CURRENT_DATE);


-- ============================================================
-- SCENARIO 4: Late Data (Source Not Arrived)
-- Simulate: source table has no data for today
-- Agent should: detect missing data, check schedule, set retry
-- ============================================================

-- No data for today in source
DELETE FROM source_layer.claims_raw WHERE load_date = CURRENT_DATE;

INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, error_message, run_date)
VALUES ('load_claims_raw', 'source_layer', 'claims_raw', 'SUCCESS', 0, 'No new records found in source for today', CURRENT_DATE);


-- ============================================================
-- SCENARIO 5: Schema Change (New Column in Source)
-- Simulate: source added a new column, staging load breaks
-- Agent should: detect mismatch, alter staging table, reload
-- ============================================================

-- Add column to source that doesn't exist in staging
ALTER TABLE source_layer.claims_raw ADD COLUMN IF NOT EXISTS service_date DATE;
UPDATE source_layer.claims_raw SET service_date = claim_date WHERE load_date = CURRENT_DATE;

INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, error_message, run_date)
VALUES ('load_claims_staged', 'staging_layer', 'claims_staged', 'FAILED', 0, 'Column count mismatch: source has 11 columns, target has 10 columns', CURRENT_DATE);
