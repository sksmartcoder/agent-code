-- ============================================================
-- Load Synthetic Good Data (Happy Path)
-- Run after 01_create_database.sql
-- This creates the baseline "everything working" state
-- ============================================================

-- ============================================================
-- SOURCE: 500 customers
-- ============================================================
INSERT INTO source_layer.customers_raw (customer_id, first_name, last_name, date_of_birth, state, zip_code, email)
SELECT
    s AS customer_id,
    'FirstName_' || s,
    'LastName_' || s,
    '1960-01-01'::DATE + (random() * 20000)::INT,
    (ARRAY['GA','FL','NY','TX','CA','OH','IL','PA','NC','SC'])[1 + (random()*9)::INT],
    LPAD((10000 + (random()*89999)::INT)::TEXT, 5, '0'),
    'user_' || s || '@example.com'
FROM generate_series(1, 500) s;

-- ============================================================
-- SOURCE: 800 policies
-- ============================================================
INSERT INTO source_layer.policies_raw (policy_id, customer_id, product_type, effective_date, expiration_date, premium_amount, status, state_code)
SELECT
    s AS policy_id,
    1 + (random() * 499)::INT AS customer_id,
    (ARRAY['ACCIDENT','HOSPITAL','CANCER','DENTAL','VISION','DISABILITY','LIFE'])[1 + (random()*6)::INT],
    '2023-01-01'::DATE + (random() * 500)::INT,
    '2026-01-01'::DATE + (random() * 365)::INT,
    20 + (random() * 180)::INT,
    (ARRAY['ACTIVE','ACTIVE','ACTIVE','ACTIVE','LAPSED','CANCELLED'])[1 + (random()*5)::INT],
    (ARRAY['GA','FL','NY','TX','CA','OH','IL','PA','NC','SC'])[1 + (random()*9)::INT]
FROM generate_series(1, 800) s;

-- ============================================================
-- SOURCE: 2000 claims
-- ============================================================
INSERT INTO source_layer.claims_raw (claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name)
SELECT
    s AS claim_id,
    p.policy_id,
    p.customer_id,
    CURRENT_DATE - (random() * 90)::INT,
    50 + (random() * 5000)::INT,
    p.product_type,
    (ARRAY['SUBMITTED','APPROVED','DENIED','PAID','PENDING'])[1 + (random()*4)::INT],
    'ICD' || LPAD((random()*999)::INT::TEXT, 3, '0'),
    'Provider_' || (1 + (random()*99)::INT)
FROM generate_series(1, 2000) s
JOIN source_layer.policies_raw p ON p.policy_id = 1 + (random() * 799)::INT
LIMIT 2000;

-- ============================================================
-- STAGING: Copy from source with hash keys
-- ============================================================
INSERT INTO staging_layer.customers_staged (customer_id, first_name, last_name, date_of_birth, state, zip_code, email, hash_key, is_valid)
SELECT customer_id, first_name, last_name, date_of_birth, state, zip_code, email,
    MD5(COALESCE(first_name,'') || COALESCE(last_name,'') || COALESCE(state,'') || COALESCE(zip_code,'')),
    TRUE
FROM source_layer.customers_raw;

INSERT INTO staging_layer.policies_staged (policy_id, customer_id, product_type, effective_date, expiration_date, premium_amount, status, state_code, hash_key, is_valid)
SELECT policy_id, customer_id, product_type, effective_date, expiration_date, premium_amount, status, state_code,
    MD5(COALESCE(product_type,'') || COALESCE(status,'') || premium_amount::TEXT),
    TRUE
FROM source_layer.policies_raw;

INSERT INTO staging_layer.claims_staged (claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name, hash_key, is_valid)
SELECT claim_id, policy_id, customer_id, claim_date, amount, claim_type, status, diagnosis_code, provider_name,
    MD5(claim_id::TEXT || COALESCE(status,'') || amount::TEXT),
    TRUE
FROM source_layer.claims_raw;

-- ============================================================
-- WORK: Enriched claims (join claims + policies + customers)
-- ============================================================
INSERT INTO work_layer.claims_enriched
SELECT
    c.claim_id, c.policy_id, c.customer_id, c.claim_date, c.amount,
    c.claim_type, c.status, c.diagnosis_code, c.provider_name,
    cu.first_name || ' ' || cu.last_name AS customer_name,
    cu.state AS customer_state,
    p.product_type, p.premium_amount, p.status AS policy_status,
    CURRENT_DATE
FROM staging_layer.claims_staged c
JOIN staging_layer.policies_staged p ON c.policy_id = p.policy_id
JOIN staging_layer.customers_staged cu ON c.customer_id = cu.customer_id;

-- ============================================================
-- DATA: Load dimensions
-- ============================================================
INSERT INTO data_layer.dim_customer (customer_id, first_name, last_name, date_of_birth, state, zip_code, effective_date, hash_key)
SELECT customer_id, first_name, last_name, date_of_birth, state, zip_code, CURRENT_DATE, hash_key
FROM staging_layer.customers_staged;

INSERT INTO data_layer.dim_policy (policy_id, customer_id, product_type, premium_amount, status, state_code, effective_date, hash_key)
SELECT policy_id, customer_id, product_type, premium_amount, status, state_code, CURRENT_DATE, hash_key
FROM staging_layer.policies_staged;

-- ============================================================
-- DATA: Load fact
-- ============================================================
INSERT INTO data_layer.fact_claims (claim_id, policy_key, customer_key, date_key, product_key, amount, claim_type, status, diagnosis_code, provider_name)
SELECT
    e.claim_id,
    dp.policy_key,
    dc.customer_key,
    TO_CHAR(e.claim_date, 'YYYYMMDD')::INT,
    pr.product_key,
    e.amount,
    e.claim_type,
    e.status,
    e.diagnosis_code,
    e.provider_name
FROM work_layer.claims_enriched e
JOIN data_layer.dim_policy dp ON e.policy_id = dp.policy_id AND dp.is_current = TRUE
JOIN data_layer.dim_customer dc ON e.customer_id = dc.customer_id AND dc.is_current = TRUE
JOIN data_layer.dim_product pr ON e.product_type = pr.product_type;

-- ============================================================
-- LOG: Record successful loads
-- ============================================================
INSERT INTO config.etl_job_log (job_name, target_schema, target_table, status, rows_inserted, start_time, end_time, run_date) VALUES
('load_customers_staged', 'staging_layer', 'customers_staged', 'SUCCESS', 500, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour 55 minutes', CURRENT_DATE),
('load_policies_staged', 'staging_layer', 'policies_staged', 'SUCCESS', 800, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour 50 minutes', CURRENT_DATE),
('load_claims_staged', 'staging_layer', 'claims_staged', 'SUCCESS', 2000, NOW() - INTERVAL '1 hour 50 minutes', NOW() - INTERVAL '1 hour 40 minutes', CURRENT_DATE),
('load_claims_enriched', 'work_layer', 'claims_enriched', 'SUCCESS', 2000, NOW() - INTERVAL '1 hour 40 minutes', NOW() - INTERVAL '1 hour 30 minutes', CURRENT_DATE),
('load_dim_customer', 'data_layer', 'dim_customer', 'SUCCESS', 500, NOW() - INTERVAL '1 hour 30 minutes', NOW() - INTERVAL '1 hour 25 minutes', CURRENT_DATE),
('load_dim_policy', 'data_layer', 'dim_policy', 'SUCCESS', 800, NOW() - INTERVAL '1 hour 25 minutes', NOW() - INTERVAL '1 hour 20 minutes', CURRENT_DATE),
('load_fact_claims', 'data_layer', 'fact_claims', 'SUCCESS', 2000, NOW() - INTERVAL '1 hour 20 minutes', NOW() - INTERVAL '1 hour 10 minutes', CURRENT_DATE);
