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
      @run_id, @publish_date, source_system, currency_code, "SOURCE_NATIVE" AS category_type, category, category_rank, items_sold, distinct_products, orders, total_sales, avg_item_price, sales_share_pct
    FROM `lumina-retail-001.lumina_stage.vw_commercial_category_performance_v1`
    UNION ALL
    SELECT 
      @run_id, 
      @publish_date, 
      "uci" AS source_system, 
      "GBP" AS currency_code, 
      category_type, 
      category, 
      DENSE_RANK() OVER (ORDER BY total_sales DESC) AS category_rank, 
      items_sold, 
      distinct_products, 
      orders, 
      total_sales, 
      avg_item_price, 
      ROUND(SAFE_DIVIDE(total_sales, SUM(total_sales) OVER ()) * 100, 2) AS sales_share_pct
    FROM (
      SELECT 
        CASE
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(POSTAGE|MANUAL|CARRIAGE|DISCOUNT|FEE)') THEN 'Postage & Fees'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(CAKE|BAKING|TEA|MUG|COFFEE|PLATE|BOWL|KITCHEN|CUTLERY|JUG|PANTRY|JAM|JAR|GLASS|BOTTLE|LUNCH BOX|LUNCH BAG|FORK|SPOON|DISH|COOK)') THEN 'Kitchen & Dining'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(LIGHT|LAMP|CANDLE|T-LIGHT|HOLDER|FRAME|CLOCK|MIRROR|WALL|DOORMAT|SIGN|CUSHION|ORNAMENT|DECORATION|CHANDELIER)') THEN 'Home Decor & Lighting'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(CHRISTMAS|XMAS|PARTY|BUNTING|BALLOON|EASTER|HALLOWEEN|SNOWFLAKE|BIRTHDAY|GARLAND)') THEN 'Seasonal & Party'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(BAG|PURSE|WALLET|TOTE|SHOPPER|SUITCASE|LUGGAGE|BACKPACK)') THEN 'Bags & Luggage'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(PAPER|CARD|NOTEBOOK|PEN|PENCIL|STICKER|CRAFT|RIBBON|WRAP|ALBUM|BOOK)') THEN 'Stationery & Crafts'
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(HEART|RETROSPOT|VINTAGE|TOY|GAME|PLUSH|TEDDY|TRINKET|DOLL|MAGIC|PUZZLE)') THEN 'Gifts & Toys'
          ELSE 'Unclassified'
        END AS category,
        CASE
          WHEN REGEXP_CONTAINS(UPPER(product_name), r'(POSTAGE|MANUAL|CARRIAGE|DISCOUNT|FEE|CAKE|BAKING|TEA|MUG|COFFEE|PLATE|BOWL|KITCHEN|CUTLERY|JUG|PANTRY|JAM|JAR|GLASS|BOTTLE|LUNCH BOX|LUNCH BAG|FORK|SPOON|DISH|COOK|LIGHT|LAMP|CANDLE|T-LIGHT|HOLDER|FRAME|CLOCK|MIRROR|WALL|DOORMAT|SIGN|CUSHION|ORNAMENT|DECORATION|CHANDELIER|CHRISTMAS|XMAS|PARTY|BUNTING|BALLOON|EASTER|HALLOWEEN|SNOWFLAKE|BIRTHDAY|GARLAND|BAG|PURSE|WALLET|TOTE|SHOPPER|SUITCASE|LUGGAGE|BACKPACK|PAPER|CARD|NOTEBOOK|PEN|PENCIL|STICKER|CRAFT|RIBBON|WRAP|ALBUM|BOOK|HEART|RETROSPOT|VINTAGE|TOY|GAME|PLUSH|TEDDY|TRINKET|DOLL|MAGIC|PUZZLE)') THEN 'DERIVED_RULE'
          ELSE 'UNCLASSIFIED'
        END AS category_type,
        SUM(quantity) AS items_sold,
        COUNT(DISTINCT source_product_id) AS distinct_products,
        COUNT(DISTINCT source_order_id) AS orders,
        ROUND(SUM(gross_sales_gbp), 2) AS total_sales,
        ROUND(SAFE_DIVIDE(SUM(gross_sales_gbp), NULLIF(SUM(quantity), 0)), 2) AS avg_item_price
      FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
      WHERE quantity > 0
      GROUP BY 1, 2
    );

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
      CASE
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(POSTAGE|MANUAL|CARRIAGE|DISCOUNT|FEE)') THEN 'Postage & Fees'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(CAKE|BAKING|TEA|MUG|COFFEE|PLATE|BOWL|KITCHEN|CUTLERY|JUG|PANTRY|JAM|JAR|GLASS|BOTTLE|LUNCH BOX|LUNCH BAG|FORK|SPOON|DISH|COOK)') THEN 'Kitchen & Dining'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(LIGHT|LAMP|CANDLE|T-LIGHT|HOLDER|FRAME|CLOCK|MIRROR|WALL|DOORMAT|SIGN|CUSHION|ORNAMENT|DECORATION|CHANDELIER)') THEN 'Home Decor & Lighting'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(CHRISTMAS|XMAS|PARTY|BUNTING|BALLOON|EASTER|HALLOWEEN|SNOWFLAKE|BIRTHDAY|GARLAND)') THEN 'Seasonal & Party'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(BAG|PURSE|WALLET|TOTE|SHOPPER|SUITCASE|LUGGAGE|BACKPACK)') THEN 'Bags & Luggage'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(PAPER|CARD|NOTEBOOK|PEN|PENCIL|STICKER|CRAFT|RIBBON|WRAP|ALBUM|BOOK)') THEN 'Stationery & Crafts'
        WHEN REGEXP_CONTAINS(UPPER(product_name), r'(HEART|RETROSPOT|VINTAGE|TOY|GAME|PLUSH|TEDDY|TRINKET|DOLL|MAGIC|PUZZLE)') THEN 'Gifts & Toys'
        ELSE 'Unclassified'
      END AS category, 
      CAST(NULL AS STRING) AS brand, 
      CAST(NULL AS STRING) AS department, 
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
