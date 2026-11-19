-- SCRIPT 01c: VALIDACIÓN DE ESQUEMA EXISTENTE CONTRA EL CONTRATO CANÓNICO (94 COLUMNAS)
-- Compara simétricamente columnas, tipos, nulabilidad, particionamiento y clustering.

BEGIN
  -- 1. VALIDACIÓN SIMÉTRICA DE LAS 94 COLUMNAS, TIPOS, NULABILIDAD Y CLUSTERING
  ASSERT (
    WITH expected_metadata AS (
      -- gold_publisher_lock (6 cols) - Sin partición, sin clustering
      SELECT "gold_publisher_lock" AS tbl, "domain" AS col, "STRING" AS typ, "NO" AS nul, "NO" AS part, CAST(NULL AS INT64) AS clus UNION ALL
      SELECT "gold_publisher_lock", "status", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_publisher_lock", "locked_by_run_id", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_publisher_lock", "fencing_token", "INT64", "NO", "NO", NULL UNION ALL
      SELECT "gold_publisher_lock", "leased_until", "TIMESTAMP", "YES", "NO", NULL UNION ALL
      SELECT "gold_publisher_lock", "last_published_at", "TIMESTAMP", "YES", "NO", NULL UNION ALL

      -- gold_release_control (5 cols) - Cluster domain
      SELECT "gold_release_control", "domain", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_release_control", "current_run_id", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_release_control", "previous_run_id", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_release_control", "status", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_release_control", "released_at", "TIMESTAMP", "NO", "NO", NULL UNION ALL

      -- gold_execution_history (10 cols) - Partition event_timestamp, Cluster domain, run_id, event_type
      SELECT "gold_execution_history", "event_id", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_execution_history", "run_id", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_execution_history", "event_sequence", "INT64", "NO", "NO", NULL UNION ALL
      SELECT "gold_execution_history", "operation_type", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_execution_history", "domain", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_execution_history", "event_type", "STRING", "NO", "NO", 3 UNION ALL
      SELECT "gold_execution_history", "event_timestamp", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_execution_history", "operator", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_execution_history", "input_fingerprint", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_execution_history", "details", "JSON", "YES", "NO", NULL UNION ALL

      -- gold_audit_results (7 cols) - Partition audit_timestamp, Cluster domain, run_id, test_name
      SELECT "gold_audit_results", "event_id", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_audit_results", "run_id", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_audit_results", "domain", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_audit_results", "audit_timestamp", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_audit_results", "test_name", "STRING", "NO", "NO", 3 UNION ALL
      SELECT "gold_audit_results", "passed", "BOOL", "NO", "NO", NULL UNION ALL
      SELECT "gold_audit_results", "details", "STRING", "YES", "NO", NULL UNION ALL

      -- gold_commercial_monthly (15 cols) - Partition publish_date, Cluster run_id, source_system, currency_code
      SELECT "gold_commercial_monthly", "run_id", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_commercial_monthly", "publish_date", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_commercial_monthly", "source_system", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_commercial_monthly", "source_label", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "currency_code", "STRING", "NO", "NO", 3 UNION ALL
      SELECT "gold_commercial_monthly", "order_month", "DATE", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "total_orders", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "total_items", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "total_product_sales", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "completed_orders", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "completed_items", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "completed_product_sales", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "avg_completed_order_value", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "completed_order_rate_pct", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_monthly", "completed_sales_share_pct", "FLOAT64", "YES", "NO", NULL UNION ALL

      -- gold_commercial_categories (13 cols) - Partition publish_date, Cluster run_id, source_system
      SELECT "gold_commercial_categories", "run_id", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_commercial_categories", "publish_date", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_commercial_categories", "source_system", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_commercial_categories", "currency_code", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "category_type", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "category", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "category_rank", "INT64", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "items_sold", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "distinct_products", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "orders", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "total_sales", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "avg_item_price", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_categories", "sales_share_pct", "FLOAT64", "YES", "NO", NULL UNION ALL

      -- gold_commercial_products (14 cols) - Partition publish_date, Cluster run_id, source_system
      SELECT "gold_commercial_products", "run_id", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_commercial_products", "publish_date", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_commercial_products", "source_system", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_commercial_products", "currency_code", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "source_product_id", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "product_name", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "category", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "brand", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "department", "STRING", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "items_sold", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "orders", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "total_sales", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "avg_item_price", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_commercial_products", "sales_rank", "INT64", "NO", "NO", NULL UNION ALL

      -- gold_logistics_dashboard (24 cols) - Partition publish_date, Cluster run_id, source_system
      SELECT "gold_logistics_dashboard", "run_id", "STRING", "NO", "NO", 1 UNION ALL
      SELECT "gold_logistics_dashboard", "publish_date", "TIMESTAMP", "NO", "YES", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "source_system", "STRING", "NO", "NO", 2 UNION ALL
      SELECT "gold_logistics_dashboard", "source_label", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "order_cohort_month", "DATE", "NO", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "total_orders", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "valid_shipments", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "valid_deliveries", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "deliveries_with_estimate", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "late_deliveries", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "valid_returns", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "invalid_shipping_sequence", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "invalid_delivery_sequence", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "delivery_without_shipment", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "future_shipments", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "future_deliveries", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "future_returns", "INT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "avg_shipping_hours", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "avg_delivery_hours", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "shipment_coverage_pct", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "delivery_coverage_pct", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "late_delivery_rate_pct", "FLOAT64", "YES", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "late_delivery_data_status", "STRING", "NO", "NO", NULL UNION ALL
      SELECT "gold_logistics_dashboard", "calculated_at", "TIMESTAMP", "NO", "NO", NULL
    ),
    actual_metadata AS (
      SELECT 
        table_name AS tbl, 
        column_name AS col, 
        data_type AS typ, 
        is_nullable AS nul,
        is_partitioning_column AS part,
        clustering_ordinal_position AS clus
      FROM `lumina-retail-001.lumina_sandbox.INFORMATION_SCHEMA.COLUMNS`
    ),
    diff_missing AS (
      SELECT * FROM expected_metadata EXCEPT DISTINCT SELECT * FROM actual_metadata
    ),
    diff_unexpected AS (
      SELECT * FROM actual_metadata EXCEPT DISTINCT SELECT * FROM expected_metadata
    )
    SELECT (SELECT COUNT(*) FROM diff_missing) = 0 
       AND (SELECT COUNT(*) FROM diff_unexpected) = 0
  ) AS "ABORT_SCHEMA: Discrepancia simétrica con el contrato canónico de 94 columnas en INFORMATION_SCHEMA.COLUMNS.";

  -- 2. VALIDACIÓN DE AUSENCIA DE TABLAS O VISTAS INESPERADAS
  ASSERT (
    WITH actual_tables AS (
      SELECT table_name 
      FROM `lumina-retail-001.lumina_sandbox.INFORMATION_SCHEMA.TABLES`
    ),
    expected_tables AS (
      SELECT "gold_publisher_lock" AS table_name UNION ALL
      SELECT "gold_release_control" UNION ALL
      SELECT "gold_execution_history" UNION ALL
      SELECT "gold_audit_results" UNION ALL
      SELECT "gold_commercial_monthly" UNION ALL
      SELECT "gold_commercial_categories" UNION ALL
      SELECT "gold_commercial_products" UNION ALL
      SELECT "gold_logistics_dashboard"
    ),
    diff_missing_tbl AS (
      SELECT table_name FROM expected_tables EXCEPT DISTINCT SELECT table_name FROM actual_tables
    ),
    diff_unexpected_tbl AS (
      SELECT table_name FROM actual_tables EXCEPT DISTINCT SELECT table_name FROM expected_tables
    )
    SELECT (SELECT COUNT(*) FROM diff_missing_tbl) = 0
       AND (SELECT COUNT(*) FROM diff_unexpected_tbl) = 0
  ) AS "ABORT_SCHEMA: Existen tablas o vistas no autorizadas o faltan tablas requeridas en lumina_sandbox.";
END;
