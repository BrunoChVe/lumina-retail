-- ==============================================================================
-- PROYECTO: LUMINA RETAIL / RETAILSMART GLOBAL
-- FUENTE: UCI Online Retail (Reino Unido / Europa) - Moneda: GBP
-- DESCRIPCIÓN: DDL de tabla staging independiente y vista de integración
-- NOTA: Preparación de sentencias. NO ejecutar en BigQuery sin aprobación previa.
-- ==============================================================================

-- 1. TABLA INDEPENDIENTE DE STAGING: stg_uci_online_retail
-- Particionada diariamente por fecha de emisión y clusterizada por orden y producto
CREATE TABLE IF NOT EXISTS `lumina-retail-001.lumina_stage.stg_uci_online_retail`
(
    source_system STRING NOT NULL,          -- 'uci'
    source_order_id STRING NOT NULL,        -- InvoiceNo
    source_item_id STRING NOT NULL,         -- InvoiceNo_lineIdx (Clave única primaria)
    source_customer_id STRING,              -- CustomerID o 'ANONYMOUS'
    source_product_id STRING,               -- StockCode
    product_name STRING,                    -- Description
    order_created_at TIMESTAMP NOT NULL,    -- InvoiceDate
    order_status STRING NOT NULL,           -- 'Complete', 'Cancelled', 'Adjusted'
    item_status STRING NOT NULL,            -- 'delivered', 'cancelled', 'non_commercial'
    quantity INT64 NOT NULL,                -- Cantidad (positivo o negativo)
    unit_price FLOAT64 NOT NULL,            -- Precio unitario en GBP
    product_sales FLOAT64 NOT NULL,         -- Importe total de línea en GBP
    gross_sales_gbp FLOAT64 NOT NULL,       -- Ventas brutas (solo positivos)
    return_sales_gbp FLOAT64 NOT NULL,      -- Devoluciones y reembolsos (negativos)
    net_sales_gbp FLOAT64 NOT NULL,         -- Venta neta (gross + return)
    freight_value FLOAT64,                  -- 0.0
    country STRING,                         -- País del comprador
    currency_code STRING NOT NULL           -- 'GBP'
)
PARTITION BY DATE(order_created_at)
CLUSTER BY source_order_id, source_product_id;


-- 2. VISTA ANALÍTICA MENSUAL DEDICADA: vw_uci_commercial_monthly
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_stage.vw_uci_commercial_monthly` AS
SELECT
    'uci' AS source_system,
    'UCI Online Retail' AS source_label,
    'GBP' AS currency_code,
    'documented' AS currency_status,
    DATE_TRUNC(DATE(order_created_at), MONTH) AS order_month,
    COUNT(DISTINCT source_order_id) AS total_orders,
    COUNT(*) AS total_items,
    ROUND(SUM(gross_sales_gbp), 2) AS total_gross_sales_gbp,
    ROUND(SUM(return_sales_gbp), 2) AS total_return_sales_gbp,
    ROUND(SUM(net_sales_gbp), 2) AS total_net_sales_gbp,
    COUNT(DISTINCT IF(order_status = 'Complete', source_order_id, NULL)) AS completed_orders,
    COUNT(DISTINCT IF(order_status = 'Cancelled', source_order_id, NULL)) AS cancelled_orders,
    ROUND(
        SAFE_DIVIDE(
            COUNT(DISTINCT IF(order_status = 'Complete', source_order_id, NULL)),
            COUNT(DISTINCT source_order_id)
        ) * 100,
        2
    ) AS completed_order_rate_pct
FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`
WHERE order_created_at IS NOT NULL
GROUP BY order_month;


-- 3. VISTA DE INTEGRACIÓN MULTISOURCE UNIFICADA: vw_sales_multisource_with_uci
-- REGLA ARQUITECTÓNICA CRÍTICA DE MONEDAS:
-- La columna 'currency_code' identifica formalmente la divisa de cada registro
-- ('BRL' para Olist, 'USD' para TheLook, 'GBP' para UCI), pero el motor SQL no
-- impide matemáticamente que una consulta ejecute SUM(product_sales) sobre monedas mixtas.
-- Es MANDATORIO que toda consulta analítica, endpoint o reporte downstream aplique
-- filtro (WHERE currency_code = '...') o agregación (GROUP BY currency_code, source_system)
-- para evitar distorsiones financieras por consolidación de monedas sin tasa de cambio.
-- Une fact_sales_multisource existente con la nueva tabla staging preservando el esquema intacto.
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_stage.vw_sales_multisource_with_uci` AS
SELECT
    source_system,
    source_order_id,
    source_item_id,
    source_customer_id,
    source_product_id,
    order_created_at,
    order_status,
    item_status,
    product_sales,
    freight_value,
    CASE
        WHEN source_system = 'olist' THEN 'BRL'
        WHEN source_system = 'thelook' THEN 'USD'
        ELSE NULL
    END AS currency_code
FROM `lumina-retail-001.lumina_stage.fact_sales_multisource`

UNION ALL

SELECT
    source_system,
    source_order_id,
    source_item_id,
    source_customer_id,
    source_product_id,
    order_created_at,
    order_status,
    item_status,
    product_sales,
    freight_value,
    currency_code
FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`;
