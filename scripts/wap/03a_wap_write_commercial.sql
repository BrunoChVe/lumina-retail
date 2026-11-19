-- SCRIPT 03a: WRITE COMMERCIAL (ATÓMICO E IDEMPOTENTE)
-- Parámetros BQ: @run_id (STRING), @publish_date (TIMESTAMP), @operator (STRING), @fingerprint (STRING)

BEGIN
  BEGIN TRANSACTION;
    -- 1. LIMPIEZA IDEMPOTENTE DE INTENTOS PREVIOS INCOMPLETOS PARA ESTE RUN_ID
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_commercial_categories` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_commercial_products` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
    WHERE run_id = @run_id AND domain = "commercial" AND operation_type = "WRITE_TABLE";

    -- 2. MATERIALIZAR gold_commercial_monthly (15 columnas)
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` (
      run_id, publish_date, source_system, source_label, currency_code, order_month,
      total_orders, total_items, total_product_sales, completed_orders, completed_items,
      completed_product_sales, avg_completed_order_value, completed_order_rate_pct, completed_sales_share_pct
    )
    SELECT 
      @run_id, 
      @publish_date, 
      source_system,
      CASE source_system 
        WHEN "olist" THEN "Olist" 
        WHEN "thelook" THEN "TheLook" 
        WHEN "uci" THEN "UCI Online Retail" 
      END AS source_label,
      CASE source_system 
        WHEN "olist" THEN "BRL" 
        WHEN "thelook" THEN "USD" 
        WHEN "uci" THEN "GBP" 
      END AS currency_code,
      order_month, 
      total_orders, 
      total_items, 
      total_product_sales, 
      completed_orders, 
      completed_items, 
      completed_product_sales, 
      avg_completed_order_value,
      SAFE_DIVIDE(completed_orders, NULLIF(total_orders, 0)) * 100 AS completed_order_rate_pct,
      SAFE_DIVIDE(completed_product_sales, NULLIF(SUM(completed_product_sales) OVER (PARTITION BY source_system), 0)) * 100 AS completed_sales_share_pct
    FROM `lumina-retail-001.lumina_stage.vw_commercial_monthly_final_v1`
    UNION ALL
    SELECT
      @run_id,
      @publish_date,
      "uci" AS source_system,
      "UCI Online Retail" AS source_label,
      "GBP" AS currency_code,
      DATE_TRUNC(DATE(order_created_at), MONTH) AS order_month,
      COUNT(DISTINCT source_order_id) AS total_orders,
      SUM(quantity) AS total_items,
      ROUND(SUM(gross_sales_gbp), 2) AS total_product_sales,
      COUNT(DISTINCT source_order_id) AS completed_orders,
      SUM(quantity) AS completed_items,
      ROUND(SUM(gross_sales_gbp), 2) AS completed_product_sales,
      ROUND(SAFE_DIVIDE(SUM(gross_sales_gbp), NULLIF(COUNT(DISTINCT source_order_id), 0)), 2) AS avg_completed_order_value,
      100.0 AS completed_order_rate_pct,
      SAFE_DIVIDE(SUM(gross_sales_gbp), NULLIF(SUM(SUM(gross_sales_gbp)) OVER (), 0)) * 100 AS completed_sales_share_pct
    FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
    WHERE quantity > 0
    GROUP BY order_month;

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES 
      (GENERATE_UUID(), @run_id, 1, "WRITE_TABLE", "commercial", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_commercial_monthly"));

    -- 3. MATERIALIZAR gold_commercial_categories (13 columnas)
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_commercial_categories` (
      run_id, publish_date, source_system, currency_code, category_type, category,
      category_rank, items_sold, distinct_products, orders, total_sales, avg_item_price, sales_share_pct
    )
    SELECT 
      @run_id, @publish_date, source_system, currency_code, "Standard" AS category_type, category, category_rank, items_sold, distinct_products, orders, total_sales, avg_item_price, sales_share_pct
    FROM `lumina-retail-001.lumina_stage.vw_commercial_category_performance_v1`
    UNION ALL
    SELECT 
      @run_id, @publish_date, "uci" AS source_system, "GBP" AS currency_code, "No_Taxonomy" AS category_type, CAST(NULL AS STRING) AS category, 1 AS category_rank, 
      SUM(quantity) AS items_sold, 
      COUNT(DISTINCT source_product_id) AS distinct_products, 
      COUNT(DISTINCT source_order_id) AS orders, 
      ROUND(SUM(gross_sales_gbp), 2) AS total_sales, 
      ROUND(SAFE_DIVIDE(SUM(gross_sales_gbp), NULLIF(SUM(quantity), 0)), 2) AS avg_item_price, 
      100.0 AS sales_share_pct
    FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail` 
    WHERE quantity > 0;

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES 
      (GENERATE_UUID(), @run_id, 2, "WRITE_TABLE", "commercial", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_commercial_categories"));

    -- 4. MATERIALIZAR gold_commercial_products (14 columnas)
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_commercial_products` (
      run_id, publish_date, source_system, currency_code, source_product_id, product_name,
      category, brand, department, items_sold, orders, total_sales, avg_item_price, sales_rank
    )
    SELECT 
      @run_id, @publish_date, source_system, currency_code, source_product_id, product_name, category, brand, department, items_sold, orders, total_sales, avg_item_price, sales_rank
    FROM `lumina-retail-001.lumina_stage.vw_commercial_product_performance_v1`
    UNION ALL
    SELECT 
      @run_id, @publish_date, "uci" AS source_system, "GBP" AS currency_code, source_product_id, product_name, 
      CAST(NULL AS STRING) AS category, CAST(NULL AS STRING) AS brand, CAST(NULL AS STRING) AS department, 
      SUM(quantity) AS items_sold, 
      COUNT(DISTINCT source_order_id) AS orders, 
      ROUND(SUM(gross_sales_gbp), 2) AS total_sales, 
      ROUND(SAFE_DIVIDE(SUM(gross_sales_gbp), NULLIF(SUM(quantity), 0)), 2) AS avg_item_price, 
      DENSE_RANK() OVER (ORDER BY SUM(gross_sales_gbp) DESC) AS sales_rank
    FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail` 
    WHERE quantity > 0 
    GROUP BY source_product_id, product_name;

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES 
      (GENERATE_UUID(), @run_id, 3, "WRITE_TABLE", "commercial", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_commercial_products"));

  COMMIT TRANSACTION;
EXCEPTION WHEN ERROR THEN
  ROLLBACK TRANSACTION;
  RAISE USING MESSAGE = @@error.message;
END;
