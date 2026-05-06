-- ============================================================
-- ETL Lineage Agent — Synthetic Database Setup
-- Run against: Amazon RDS PostgreSQL or any PostgreSQL
-- Creates a 4-layer ETL pipeline with lineage metadata
-- ============================================================

-- ============================================================
-- SCHEMAS (4 ETL layers + config)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS source_layer;
CREATE SCHEMA IF NOT EXISTS staging_layer;
CREATE SCHEMA IF NOT EXISTS work_layer;
CREATE SCHEMA IF NOT EXISTS data_layer;
CREATE SCHEMA IF NOT EXISTS config;

-- ============================================================
-- CONFIG: ETL Lineage Metadata
-- ============================================================
CREATE TABLE config.etl_lineage (
    lineage_id SERIAL PRIMARY KEY,
    target_schema VARCHAR(50),
    target_table VARCHAR(100),
    source_schema VARCHAR(50),
    source_table VARCHAR(100),
    transform_type VARCHAR(20),
    join_keys VARCHAR(200),
    load_frequency VARCHAR(20),
    description VARCHAR(500)
);

INSERT INTO config.etl_lineage (target_schema, target_table, source_schema, source_table, transform_type, join_keys, load_frequency, description) VALUES
('staging_layer', 'claims_staged', 'source_layer', 'claims_raw', 'direct_copy', 'claim_id', 'daily', 'Raw claims validated and staged'),
('staging_layer', 'policies_staged', 'source_layer', 'policies_raw', 'direct_copy', 'policy_id', 'daily', 'Raw policies validated and staged'),
('staging_layer', 'customers_staged', 'source_layer', 'customers_raw', 'direct_copy', 'customer_id', 'daily', 'Raw customers validated and staged'),
('work_layer', 'claims_enriched', 'staging_layer', 'claims_staged', 'merge_join', 'claim_id', 'daily', 'Claims enriched with policy and customer data'),
('work_layer', 'claims_enriched', 'staging_layer', 'policies_staged', 'merge_join', 'policy_id', 'daily', 'Policy data joined to claims'),
('work_layer', 'claims_enriched', 'staging_layer', 'customers_staged', 'merge_join', 'customer_id', 'daily', 'Customer data joined to claims'),
('data_layer', 'fact_claims', 'work_layer', 'claims_enriched', 'merge_scd', 'claim_id', 'daily', 'Final claims fact with surrogate keys'),
('data_layer', 'dim_policy', 'staging_layer', 'policies_staged', 'merge_scd2', 'policy_id', 'daily', 'Policy dimension with SCD Type 2'),
('data_layer', 'dim_customer', 'staging_layer', 'customers_staged', 'merge_scd2', 'customer_id', 'daily', 'Customer dimension with SCD Type 2'),
('data_layer', 'dim_date', 'config', 'date_seed', 'generate', 'date_key', 'static', 'Date dimension - generated once'),
('data_layer', 'dim_product', 'staging_layer', 'policies_staged', 'distinct', 'product_type', 'daily', 'Product dimension derived from policies');

-- ============================================================
-- CONFIG: ETL Job Log
-- ============================================================
CREATE TABLE config.etl_job_log (
    job_id SERIAL PRIMARY KEY,
    job_name VARCHAR(100),
    target_schema VARCHAR(50),
    target_table VARCHAR(100),
    status VARCHAR(20),
    rows_read INT DEFAULT 0,
    rows_inserted INT DEFAULT 0,
    rows_updated INT DEFAULT 0,
    rows_rejected INT DEFAULT 0,
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP,
    error_message TEXT,
    run_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- CONFIG: Data Quality Rules
-- ============================================================
CREATE TABLE config.data_quality_rules (
    rule_id SERIAL PRIMARY KEY,
    target_schema VARCHAR(50),
    target_table VARCHAR(100),
    rule_type VARCHAR(30),
    rule_sql TEXT,
    threshold DECIMAL(10,2),
    severity VARCHAR(10),
    description VARCHAR(500)
);

INSERT INTO config.data_quality_rules VALUES
(1, 'data_layer', 'fact_claims', 'row_count_min', 'SELECT COUNT(*) FROM data_layer.fact_claims WHERE load_date = CURRENT_DATE', 100, 'CRITICAL', 'Fact claims must have at least 100 rows daily'),
(2, 'data_layer', 'fact_claims', 'no_duplicates', 'SELECT claim_id, COUNT(*) FROM data_layer.fact_claims GROUP BY claim_id HAVING COUNT(*) > 1', 0, 'CRITICAL', 'No duplicate claim_ids allowed'),
(3, 'data_layer', 'fact_claims', 'no_nulls', 'SELECT COUNT(*) FROM data_layer.fact_claims WHERE amount IS NULL AND load_date = CURRENT_DATE', 0, 'HIGH', 'No null amounts in claims'),
(4, 'data_layer', 'fact_claims', 'row_count_variance', 'SELECT ABS(today.cnt - yesterday.cnt) * 100.0 / yesterday.cnt FROM (SELECT COUNT(*) cnt FROM data_layer.fact_claims WHERE load_date = CURRENT_DATE) today, (SELECT COUNT(*) cnt FROM data_layer.fact_claims WHERE load_date = CURRENT_DATE - 1) yesterday', 50, 'HIGH', 'Row count should not vary more than 50% day over day'),
(5, 'staging_layer', 'claims_staged', 'no_duplicates', 'SELECT claim_id, COUNT(*) FROM staging_layer.claims_staged WHERE load_date = CURRENT_DATE GROUP BY claim_id HAVING COUNT(*) > 1', 0, 'CRITICAL', 'No duplicate claim_ids in staging'),
(6, 'data_layer', 'dim_policy', 'single_current', 'SELECT policy_id, COUNT(*) FROM data_layer.dim_policy WHERE is_current = true GROUP BY policy_id HAVING COUNT(*) > 1', 0, 'CRITICAL', 'Only one current record per policy (SCD2)');

-- ============================================================
-- SOURCE LAYER: Raw data (simulates files landing)
-- ============================================================
CREATE TABLE source_layer.claims_raw (
    claim_id INT,
    policy_id INT,
    customer_id INT,
    claim_date DATE,
    amount DECIMAL(12,2),
    claim_type VARCHAR(20),
    status VARCHAR(20),
    diagnosis_code VARCHAR(10),
    provider_name VARCHAR(100),
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE source_layer.policies_raw (
    policy_id INT,
    customer_id INT,
    product_type VARCHAR(30),
    effective_date DATE,
    expiration_date DATE,
    premium_amount DECIMAL(10,2),
    status VARCHAR(20),
    state_code VARCHAR(5),
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE source_layer.customers_raw (
    customer_id INT,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    date_of_birth DATE,
    state VARCHAR(5),
    zip_code VARCHAR(10),
    email VARCHAR(100),
    load_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- STAGING LAYER: Validated and cleaned
-- ============================================================
CREATE TABLE staging_layer.claims_staged (
    claim_id INT,
    policy_id INT,
    customer_id INT,
    claim_date DATE,
    amount DECIMAL(12,2),
    claim_type VARCHAR(20),
    status VARCHAR(20),
    diagnosis_code VARCHAR(10),
    provider_name VARCHAR(100),
    hash_key VARCHAR(64),
    is_valid BOOLEAN DEFAULT TRUE,
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE staging_layer.policies_staged (
    policy_id INT,
    customer_id INT,
    product_type VARCHAR(30),
    effective_date DATE,
    expiration_date DATE,
    premium_amount DECIMAL(10,2),
    status VARCHAR(20),
    state_code VARCHAR(5),
    hash_key VARCHAR(64),
    is_valid BOOLEAN DEFAULT TRUE,
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE staging_layer.customers_staged (
    customer_id INT,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    date_of_birth DATE,
    state VARCHAR(5),
    zip_code VARCHAR(10),
    email VARCHAR(100),
    hash_key VARCHAR(64),
    is_valid BOOLEAN DEFAULT TRUE,
    load_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- WORK LAYER: Enriched and transformed
-- ============================================================
CREATE TABLE work_layer.claims_enriched (
    claim_id INT,
    policy_id INT,
    customer_id INT,
    claim_date DATE,
    amount DECIMAL(12,2),
    claim_type VARCHAR(20),
    status VARCHAR(20),
    diagnosis_code VARCHAR(10),
    provider_name VARCHAR(100),
    customer_name VARCHAR(100),
    customer_state VARCHAR(5),
    product_type VARCHAR(30),
    premium_amount DECIMAL(10,2),
    policy_status VARCHAR(20),
    load_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- DATA LAYER: Star Schema (final)
-- ============================================================
CREATE TABLE data_layer.dim_date (
    date_key INT PRIMARY KEY,
    cal_date DATE,
    day_name VARCHAR(10),
    month_name VARCHAR(10),
    quarter VARCHAR(5),
    year INT,
    is_business_day BOOLEAN,
    is_holiday BOOLEAN
);

CREATE TABLE data_layer.dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id INT,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    date_of_birth DATE,
    state VARCHAR(5),
    zip_code VARCHAR(10),
    effective_date DATE,
    expiration_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    hash_key VARCHAR(64),
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE data_layer.dim_policy (
    policy_key SERIAL PRIMARY KEY,
    policy_id INT,
    customer_id INT,
    product_type VARCHAR(30),
    premium_amount DECIMAL(10,2),
    status VARCHAR(20),
    state_code VARCHAR(5),
    effective_date DATE,
    expiration_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    hash_key VARCHAR(64),
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE data_layer.dim_product (
    product_key SERIAL PRIMARY KEY,
    product_type VARCHAR(30),
    product_name VARCHAR(100),
    product_category VARCHAR(50)
);

CREATE TABLE data_layer.fact_claims (
    claim_key SERIAL PRIMARY KEY,
    claim_id INT,
    policy_key INT,
    customer_key INT,
    date_key INT,
    product_key INT,
    amount DECIMAL(12,2),
    claim_type VARCHAR(20),
    status VARCHAR(20),
    diagnosis_code VARCHAR(10),
    provider_name VARCHAR(100),
    load_date DATE DEFAULT CURRENT_DATE
);

-- ============================================================
-- SEED DATA: Date Dimension
-- ============================================================
INSERT INTO data_layer.dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
    d AS cal_date,
    TO_CHAR(d, 'Day') AS day_name,
    TO_CHAR(d, 'Month') AS month_name,
    'Q' || EXTRACT(QUARTER FROM d) AS quarter,
    EXTRACT(YEAR FROM d)::INT AS year,
    EXTRACT(DOW FROM d) NOT IN (0, 6) AS is_business_day,
    FALSE AS is_holiday
FROM generate_series('2024-01-01'::DATE, '2025-12-31'::DATE, '1 day') d;

-- ============================================================
-- SEED DATA: Products
-- ============================================================
INSERT INTO data_layer.dim_product (product_type, product_name, product_category) VALUES
('ACCIDENT', 'Accident Gold Plan', 'Supplemental'),
('HOSPITAL', 'Hospital Indemnity Plan', 'Supplemental'),
('CANCER', 'Cancer Protection Plan', 'Supplemental'),
('DENTAL', 'Dental Advantage Plan', 'Dental/Vision'),
('VISION', 'Vision Care Plan', 'Dental/Vision'),
('DISABILITY', 'Short-Term Disability', 'Disability'),
('LIFE', 'Term Life Plan', 'Life');
