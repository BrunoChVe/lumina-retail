-- SCRIPT 04b: AUDIT LOGISTICS
-- Inyección BQ Params: @run_id (STRING), @audit_timestamp (TIMESTAMP), @catalog_version (STRING)

BEGIN
  DELETE FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` 
  WHERE run_id = @run_id AND domain = "logistics";

  -- TEST 1: TEST_LOG_UCI_EXCLUDED
  -- Comprueba exclusión estricta de UCI en logística
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "logistics", @audit_timestamp, "TEST_LOG_UCI_EXCLUDED",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS uci_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` 
  WHERE run_id = @run_id AND source_system = "uci";

  -- TEST 2: TEST_LOG_SOURCES_ALLOWED
  -- Comprueba que solo existan olist y thelook
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "logistics", @audit_timestamp, "TEST_LOG_SOURCES_ALLOWED",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS illegal_sources, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` 
  WHERE run_id = @run_id AND source_system NOT IN ("olist", "thelook");

  -- TEST 3: TEST_LOG_PK_NOT_NULL
  -- Comprueba claves primarias lógicas no nulas
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "logistics", @audit_timestamp, "TEST_LOG_PK_NOT_NULL",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS null_pks, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` 
  WHERE run_id = @run_id AND (source_system IS NULL OR order_cohort_month IS NULL);

  -- TEST 4: TEST_LOG_UNIQUENESS
  -- Comprueba unicidad de la cohorte mensual por fuente
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "logistics", @audit_timestamp, "TEST_LOG_UNIQUENESS",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS duplicate_groups, @catalog_version AS cat))
  FROM (
    SELECT source_system, order_cohort_month 
    FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` 
    WHERE run_id = @run_id 
    GROUP BY 1, 2 
    HAVING COUNT(*) > 1
  );
END;
