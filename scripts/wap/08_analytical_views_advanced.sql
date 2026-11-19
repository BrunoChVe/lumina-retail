-- 5. COMMERCIAL COUNTRIES
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_commercial_countries` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
),
uci_countries AS (
  SELECT 'uci' AS source_system, country, count(distinct source_order_id) as orders, sum(gross_sales_gbp) as gross_sales, 'GBP' as currency_code
  FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail` WHERE quantity > 0 GROUP BY 1, 2
),
thelook_countries AS (
  SELECT 'thelook' AS source_system, u.country, count(distinct f.source_order_id) as orders, sum(f.product_sales) as gross_sales, 'USD' as currency_code
  FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` f
  JOIN `bigquery-public-data.thelook_ecommerce.users` u ON CAST(f.source_customer_id AS INT64) = u.id
  WHERE f.source_system = 'thelook'
  GROUP BY 1, 2
),
olist_countries AS (
  SELECT 'olist' AS source_system, 'Brazil' AS country, count(distinct source_order_id) as orders, sum(product_sales) as gross_sales, 'BRL' as currency_code
  FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` WHERE source_system = 'olist' GROUP BY 1, 2
),
all_countries AS (
  SELECT * FROM uci_countries UNION ALL SELECT * FROM thelook_countries UNION ALL SELECT * FROM olist_countries
)
SELECT a.* 
FROM all_countries a
CROSS JOIN current_gold_run;

-- 6. COMMERCIAL CUSTOMERS
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_commercial_customers` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
),
all_customers AS (
  SELECT 'uci' AS source_system, source_customer_id as customer_id, count(distinct source_order_id) as orders, sum(gross_sales_gbp) as gross_sales, 'GBP' as currency_code
  FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail` WHERE quantity > 0 AND source_customer_id != 'ANONYMOUS' GROUP BY 1, 2
  UNION ALL
  SELECT source_system, source_customer_id as customer_id, count(distinct source_order_id) as orders, sum(product_sales) as gross_sales, CASE WHEN source_system = 'olist' THEN 'BRL' ELSE 'USD' END as currency_code
  FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` GROUP BY 1, 2
)
SELECT a.* 
FROM all_customers a
CROSS JOIN current_gold_run;

-- 7. COMMERCIAL CANCELLATIONS & RETURNS
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_sandbox.vw_commercial_cancellations` AS
WITH current_gold_run AS (
  SELECT current_run_id FROM `lumina-retail-001.lumina_sandbox.gold_release_control` WHERE domain = 'commercial' AND status = 'PUBLISHED'
),
uci_cancels AS (
  SELECT 'uci' AS source_system, 
         countif(source_order_id like 'C%') as canceled_orders, 
         sum(case when quantity < 0 then abs(quantity) * unit_price else 0 end) as return_sales,
         countif(quantity < 0) as negative_adjustments,
         'GBP' as currency_code
  FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
),
thelook_cancels AS (
  SELECT 'thelook' AS source_system, 
         count(distinct case when order_status = 'Cancelled' then source_order_id end) as canceled_orders,
         sum(case when order_status = 'Returned' then product_sales else 0 end) as return_sales,
         count(distinct case when order_status = 'Returned' then source_order_id end) as negative_adjustments,
         'USD' as currency_code
  FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` WHERE source_system = 'thelook'
),
olist_cancels AS (
  SELECT 'olist' AS source_system, 
         count(distinct case when order_status = 'canceled' then source_order_id end) as canceled_orders,
         0.0 as return_sales,
         0 as negative_adjustments,
         'BRL' as currency_code
  FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` WHERE source_system = 'olist'
),
all_cancels AS (
  SELECT * FROM uci_cancels UNION ALL SELECT * FROM thelook_cancels UNION ALL SELECT * FROM olist_cancels
)
SELECT a.* 
FROM all_cancels a
CROSS JOIN current_gold_run;
