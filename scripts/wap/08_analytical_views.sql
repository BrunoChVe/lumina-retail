-- 1. STORE DIMENSION
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_store_dimension` AS
SELECT 'olist' AS store_id, 'Olist Marketplace' AS store_name, 'Brasil' AS location, 'Marketplace' AS store_type, 'BRL' as currency_code UNION ALL
SELECT 'thelook' AS store_id, 'TheLook Global' AS store_name, 'USA/Internacional' AS location, 'eCommerce' AS store_type, 'USD' as currency_code UNION ALL
SELECT 'uci' AS store_id, 'UCI Retail' AS store_name, 'Reino Unido/Europa' AS location, 'eCommerce' AS store_type, 'GBP' as currency_code;

-- 2. STORE COMMERCIAL PERFORMANCE
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_store_commercial_performance` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
),
uci_returns AS (
   SELECT 
     'uci' as source_system, 
     DATE(EXTRACT(YEAR FROM order_created_at), EXTRACT(MONTH FROM order_created_at), 1) as order_month, 
     COUNT(DISTINCT source_order_id) as total_returned_orders,
     SUM(ABS(quantity) * unit_price) as total_returns_amount
   FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
   WHERE quantity < 0
   GROUP BY 1, 2
)
SELECT 
  c.source_system AS store_id,
  c.order_month,
  c.currency_code,
  c.total_orders,
  c.completed_orders,
  c.total_product_sales as gross_sales,
  (c.total_product_sales - IFNULL(r.total_returns_amount, 0)) as net_sales,
  IFNULL(r.total_returned_orders, 0) as total_returns
FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` c
CROSS JOIN current_gold_run
LEFT JOIN uci_returns r ON c.source_system = r.source_system AND c.order_month = r.order_month
WHERE c.run_id = current_gold_run.current_run_id;

-- 3. STORE LOGISTICS PERFORMANCE
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_store_logistics_performance` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'logistics' AND status = 'PUBLISHED'
)
SELECT 
  source_system AS store_id,
  source_label AS store_name,
  order_cohort_month,
  total_orders,
  valid_shipments,
  valid_deliveries,
  valid_returns,
  late_deliveries,
  shipment_coverage_pct,
  delivery_coverage_pct,
  late_delivery_rate_pct
FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` c
CROSS JOIN current_gold_run
WHERE c.run_id = current_gold_run.current_run_id;

-- 4. PREDICTIVE CATEGORY PERFORMANCE
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_predictive_category_performance` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'predictive' AND status = 'PUBLISHED'
)
SELECT 
  categoria,
  SUM(actual) as total_actual_demand,
  SUM(prediccion) as total_predicted_demand,
  SUM(error_absoluto) as total_absolute_error,
  SAFE_DIVIDE(SUM(error_absoluto), SUM(actual)) * 100 as category_wape_pct
FROM `lumina-retail-001.lumina_sandbox.gold_predictive_predictions` p
CROSS JOIN current_gold_run
WHERE p.run_id = current_gold_run.current_run_id
GROUP BY categoria;

