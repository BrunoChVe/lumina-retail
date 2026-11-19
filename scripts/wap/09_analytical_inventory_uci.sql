-- 1. CATÁLOGO DE PRODUCTOS E INVENTARIO ANALÍTICO UCI (Nivel Producto)
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_uci_analytical_product_catalog` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
),
product_metrics AS (
  SELECT 
    source_product_id AS stock_code,
    MAX(product_name) AS description,
    COUNT(DISTINCT source_order_id) AS total_transactions,
    SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS units_sold,
    SUM(CASE WHEN quantity < 0 THEN ABS(quantity) ELSE 0 END) AS units_returned,
    SUM(quantity) AS units_net,
    SUM(gross_sales_gbp) AS gross_revenue_gbp,
    SAFE_DIVIDE(SUM(gross_sales_gbp), SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END)) AS avg_unit_price,
    MIN(unit_price) AS min_unit_price,
    MAX(unit_price) AS max_unit_price,
    MIN(order_created_at) AS first_sale_date,
    MAX(order_created_at) AS last_sale_date,
    COUNT(DISTINCT DATE_TRUNC(DATE(order_created_at), MONTH)) AS active_months,
    COUNT(DISTINCT country) AS countries_present
  FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
  GROUP BY source_product_id
),
abc_classification AS (
  SELECT 
    *,
    SAFE_DIVIDE(units_sold, active_months) AS avg_monthly_demand,
    SUM(gross_revenue_gbp) OVER(ORDER BY gross_revenue_gbp DESC) / SUM(gross_revenue_gbp) OVER() AS cum_revenue_pct
  FROM product_metrics
  WHERE units_sold > 0
)
SELECT 
  a.*,
  CASE 
    WHEN cum_revenue_pct <= 0.70 THEN 'A'
    WHEN cum_revenue_pct <= 0.90 THEN 'B'
    ELSE 'C'
  END AS abc_class
FROM abc_classification a
CROSS JOIN current_gold_run;

-- 2. INVENTARIO ANALÍTICO POR PAÍS
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_uci_analytical_inventory_country` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
)
SELECT 
  country,
  source_product_id AS stock_code,
  MAX(product_name) AS description,
  COUNT(DISTINCT source_order_id) AS total_transactions,
  SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS units_sold,
  SUM(CASE WHEN quantity < 0 THEN ABS(quantity) ELSE 0 END) AS units_returned,
  SUM(quantity) AS units_net,
  SUM(gross_sales_gbp) AS gross_revenue_gbp,
  SAFE_DIVIDE(SUM(gross_sales_gbp), SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END)) AS avg_unit_price
FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
CROSS JOIN current_gold_run
GROUP BY country, source_product_id;

-- 3. EVOLUCIÓN HISTÓRICA MENSUAL
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_uci_analytical_inventory_monthly` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
)
SELECT 
  DATE_TRUNC(DATE(order_created_at), MONTH) AS sales_month,
  source_product_id AS stock_code,
  country,
  COUNT(DISTINCT source_order_id) AS total_transactions,
  SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) AS units_sold,
  SUM(CASE WHEN quantity < 0 THEN ABS(quantity) ELSE 0 END) AS units_returned,
  SUM(quantity) AS units_net,
  SUM(gross_sales_gbp) AS gross_revenue_gbp,
  SAFE_DIVIDE(SUM(gross_sales_gbp), SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END)) AS avg_unit_price
FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
CROSS JOIN current_gold_run
GROUP BY sales_month, source_product_id, country;
