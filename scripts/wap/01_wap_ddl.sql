-- SCRIPT 01: DDL CANÓNICO WAP-02.1 (94 COLUMNAS EXACTAS)
CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_publisher_lock` (
  domain STRING NOT NULL OPTIONS(description="Dominio lógico (commercial, logistics)"),
  status STRING NOT NULL OPTIONS(description="FREE o LOCKED"),
  locked_by_run_id STRING OPTIONS(description="UUID del proceso orquestador dueño del lease"),
  fencing_token INT64 NOT NULL OPTIONS(description="Token monotónico anti-zombie"),
  leased_until TIMESTAMP OPTIONS(description="Expiración del lease en reloj de BQ"),
  last_published_at TIMESTAMP OPTIONS(description="Último COMMIT exitoso")
);

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_release_control` (
  domain STRING NOT NULL OPTIONS(description="Dominio lógico"),
  current_run_id STRING OPTIONS(description="Versión activa productiva"),
  previous_run_id STRING OPTIONS(description="Versión preservada para rollback"),
  status STRING NOT NULL OPTIONS(description="EMPTY o PUBLISHED"),
  released_at TIMESTAMP NOT NULL OPTIONS(description="Timestamp del cambio de versión")
) CLUSTER BY domain;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_execution_history` (
  event_id STRING NOT NULL OPTIONS(description="UUID evento traza"),
  run_id STRING NOT NULL OPTIONS(description="UUID global de la ejecución"),
  event_sequence INT64 NOT NULL OPTIONS(description="Orden del evento"),
  operation_type STRING NOT NULL OPTIONS(description="ACQUIRE, WRITE_TABLE, AUDIT, PUBLISH, ROLLBACK"),
  domain STRING NOT NULL,
  event_type STRING NOT NULL OPTIONS(description="START, SUCCESS, FAILURE, CONFLICT"),
  event_timestamp TIMESTAMP NOT NULL OPTIONS(description="Timestamp del orquestador"),
  operator STRING NOT NULL OPTIONS(description="Identidad IAM"),
  input_fingerprint STRING OPTIONS(description="Firma determinista operativa"),
  details JSON OPTIONS(description="Objeto JSON extendido")
) PARTITION BY DATE(event_timestamp) CLUSTER BY domain, run_id, event_type;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_audit_results` (
  event_id STRING NOT NULL OPTIONS(description="UUID evento auditoría"),
  run_id STRING NOT NULL OPTIONS(description="UUID versión evaluada"),
  domain STRING NOT NULL,
  audit_timestamp TIMESTAMP NOT NULL OPTIONS(description="Inicio del test"),
  test_name STRING NOT NULL OPTIONS(description="Regla canónica del catálogo"),
  passed BOOL NOT NULL OPTIONS(description="TRUE o FALSE estricto"),
  details STRING OPTIONS(description="Métricas en formato STRING")
) PARTITION BY DATE(audit_timestamp) CLUSTER BY domain, run_id, test_name;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` (
  run_id STRING NOT NULL, publish_date TIMESTAMP NOT NULL, source_system STRING NOT NULL, source_label STRING NOT NULL, currency_code STRING NOT NULL, order_month DATE NOT NULL, total_orders INT64, total_items INT64, total_product_sales FLOAT64, completed_orders INT64, completed_items INT64, completed_product_sales FLOAT64, avg_completed_order_value FLOAT64, completed_order_rate_pct FLOAT64, completed_sales_share_pct FLOAT64
) PARTITION BY DATE(publish_date) CLUSTER BY run_id, source_system, currency_code;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_commercial_categories` (
  run_id STRING NOT NULL, publish_date TIMESTAMP NOT NULL, source_system STRING NOT NULL, currency_code STRING NOT NULL, category_type STRING NOT NULL, category STRING, category_rank INT64 NOT NULL, items_sold INT64, distinct_products INT64, orders INT64, total_sales FLOAT64, avg_item_price FLOAT64, sales_share_pct FLOAT64
) PARTITION BY DATE(publish_date) CLUSTER BY run_id, source_system;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_commercial_products` (
  run_id STRING NOT NULL, publish_date TIMESTAMP NOT NULL, source_system STRING NOT NULL, currency_code STRING NOT NULL, source_product_id STRING, product_name STRING, category STRING, brand STRING, department STRING, items_sold INT64, orders INT64, total_sales FLOAT64, avg_item_price FLOAT64, sales_rank INT64 NOT NULL
) PARTITION BY DATE(publish_date) CLUSTER BY run_id, source_system;

CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` (
  run_id STRING NOT NULL, publish_date TIMESTAMP NOT NULL, source_system STRING NOT NULL, source_label STRING NOT NULL, order_cohort_month DATE NOT NULL, total_orders INT64, valid_shipments INT64, valid_deliveries INT64, deliveries_with_estimate INT64, late_deliveries INT64, valid_returns INT64, invalid_shipping_sequence INT64, invalid_delivery_sequence INT64, delivery_without_shipment INT64, future_shipments INT64, future_deliveries INT64, future_returns INT64, avg_shipping_hours FLOAT64, avg_delivery_hours FLOAT64, shipment_coverage_pct FLOAT64, delivery_coverage_pct FLOAT64, late_delivery_rate_pct FLOAT64, late_delivery_data_status STRING NOT NULL, calculated_at TIMESTAMP NOT NULL
) PARTITION BY DATE(publish_date) CLUSTER BY run_id, source_system;
