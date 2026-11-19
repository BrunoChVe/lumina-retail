-- SCRIPT 04a: AUDIT COMMERCIAL
-- Inyección BQ Params: @run_id (STRING), @audit_timestamp (TIMESTAMP), @catalog_version (STRING)

BEGIN
  -- 1. LIMPIEZA PREVIA IDEMPOTENTE PARA ESTE RUN_ID
  DELETE FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` 
  WHERE run_id = @run_id AND domain = "commercial";

  -- TEST 1: TEST_COMM_CURRENCY_ISOLATION
  -- Comprueba aislamiento estricto de divisas (Olist=BRL, TheLook=USD, UCI=GBP)
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_CURRENCY_ISOLATION",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly`
  WHERE run_id = @run_id 
    AND (
      (source_system = "olist" AND currency_code != "BRL") OR
      (source_system = "thelook" AND currency_code != "USD") OR
      (source_system = "uci" AND currency_code != "GBP") OR
      currency_code IS NULL
    );

  -- TEST 2: TEST_COMM_PK_MONTHLY_NOT_NULL
  -- Comprueba que las claves primarias lógicas no contengan NULL
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_PK_MONTHLY_NOT_NULL",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly`
  WHERE run_id = @run_id 
    AND (source_system IS NULL OR order_month IS NULL OR currency_code IS NULL);

  -- TEST 3: TEST_COMM_MONTHLY_GRAIN_UNIQUENESS
  -- Comprueba que no existan duplicados en la granularidad (source_system, order_month)
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_MONTHLY_GRAIN_UNIQUENESS",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS duplicate_groups, @catalog_version AS cat))
  FROM (
    SELECT source_system, order_month 
    FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` 
    WHERE run_id = @run_id 
    GROUP BY 1, 2 
    HAVING COUNT(*) > 1
  );

  -- TEST 4: TEST_COMM_UCI_NO_INVENTED_CATEGORIES
  -- Comprueba que UCI no tenga categorías inventadas (debe ser NULL)
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_UCI_NO_INVENTED_CATEGORIES",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_commercial_categories`
  WHERE run_id = @run_id 
    AND source_system = "uci" 
    AND category IS NOT NULL;

  -- TEST 5: TEST_COMM_UCI_GRANULARITY_AND_PRESERVATION
  -- Comprueba preservación 1:1 de descripciones y unidades vendidas de UCI sin centinelas, null-safe nativo
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_UCI_GRANULARITY_AND_PRESERVATION",
    (discrepancies = 0),
    TO_JSON_STRING(STRUCT(discrepancies, @catalog_version AS cat))
  FROM (
    WITH uci_src AS (
      SELECT source_product_id, product_name, SUM(quantity) AS raw_qty
      FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
      WHERE quantity > 0
      GROUP BY 1, 2
    ),
    uci_gld AS (
      SELECT source_product_id, product_name, SUM(items_sold) AS gold_qty
      FROM `lumina-retail-001.lumina_sandbox.gold_commercial_products`
      WHERE run_id = @run_id AND source_system = "uci"
      GROUP BY 1, 2
    ),
    missing_in_gold AS (
      SELECT source_product_id, product_name, raw_qty FROM uci_src
      EXCEPT DISTINCT
      SELECT source_product_id, product_name, gold_qty FROM uci_gld
    ),
    extra_in_gold AS (
      SELECT source_product_id, product_name, gold_qty FROM uci_gld
      EXCEPT DISTINCT
      SELECT source_product_id, product_name, raw_qty FROM uci_src
    ),
    dups_in_gold AS (
      SELECT source_product_id, product_name FROM uci_gld GROUP BY 1, 2 HAVING COUNT(*) > 1
    )
    SELECT (SELECT COUNT(*) FROM missing_in_gold) + (SELECT COUNT(*) FROM extra_in_gold) + (SELECT COUNT(*) FROM dups_in_gold) AS discrepancies
  );

  -- TEST 6: TEST_COMM_INTEGRITY_MONTHLY_VS_PRODUCTS
  -- Compara la suma de unidades entre monthly (total_items) y products (items_sold) por fuente
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results` (event_id, run_id, domain, audit_timestamp, test_name, passed, details)
  SELECT 
    GENERATE_UUID(), @run_id, "commercial", @audit_timestamp, "TEST_COMM_INTEGRITY_MONTHLY_VS_PRODUCTS",
    (COUNT(*) = 0),
    TO_JSON_STRING(STRUCT(COUNT(*) AS discrepancies, @catalog_version AS cat))
  FROM (
    WITH m AS (
      SELECT source_system, SUM(total_items) AS m_items 
      FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` 
      WHERE run_id = @run_id 
      GROUP BY 1
    ),
    p AS (
      SELECT source_system, SUM(items_sold) AS p_items 
      FROM `lumina-retail-001.lumina_sandbox.gold_commercial_products` 
      WHERE run_id = @run_id 
      GROUP BY 1
    )
    SELECT 1 
    FROM m 
    FULL OUTER JOIN p ON m.source_system = p.source_system
    WHERE m.source_system IS NULL                -- Fuente solo en productos
       OR p.source_system IS NULL                -- Fuente solo en mensual
       OR m.m_items IS NULL                      -- Total mensual nulo
       OR p.p_items IS NULL                      -- Total productos nulo
       OR m.m_items != p.p_items                 -- Discrepancia en suma de ítems
  );
END;
