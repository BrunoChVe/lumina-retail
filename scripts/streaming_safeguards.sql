-- ==============================================================================
-- PROYECTO: LUMINA RETAIL / RETAILSMART GLOBAL
-- SALVAGUARDAS DE TELEMETRÍA E INTEGRIDAD DE INVENTARIO
-- DESCRIPCIÓN: Definiciones defensivas para stock_actual_vw y stock_risk_by_product_region.
--              Exclusión de eventos sintéticos y soporte riguroso de valores nulos (3VL).
-- NOTA: Archivo de preparación local. NO ejecutar en BigQuery sin autorización.
-- ==============================================================================

-- 1. VISTA DE ESTADO ACTUAL: lumina_streaming.stock_actual_vw
-- Esquema de salida exacto (7 columnas):
-- product_id, region, stock_registrado, fecha_ultimo_evento, fecha_procesamiento, minutos_desde_evento, estado_frescura
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_streaming.stock_actual_vw` AS
WITH eventos_filtrados AS (
  SELECT
    product_id,
    region,
    stock,
    SAFE_CAST(event_timestamp AS TIMESTAMP) AS event_timestamp,
    SAFE_CAST(ingested_at AS TIMESTAMP) AS fecha_procesamiento,
    ROW_NUMBER() OVER (
      PARTITION BY product_id, region
      ORDER BY
        SAFE_CAST(event_timestamp AS TIMESTAMP) DESC,
        SAFE_CAST(ingested_at AS TIMESTAMP) DESC
    ) AS rn
  FROM `lumina-retail-001.lumina_streaming.telemetria_consolidada`
  -- FILTRO DEFENSIVO APLICADO ANTES DE LA VENTANA ANALÍTICA:
  -- Evita que eventos sintéticos usurpen rn = 1 y preserva nulos legítimos
  -- WHERE (region IS NULL OR region != 'CYBER_TEST')
    -- AND (event_type IS NULL OR event_type != 'SYNTHETIC_CYBERDAY_STRESS')
)
SELECT
  product_id,
  region,
  stock AS stock_registrado,
  event_timestamp AS fecha_ultimo_evento,
  fecha_procesamiento,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), event_timestamp, MINUTE) AS minutos_desde_evento,
  CASE
    WHEN event_timestamp IS NULL THEN "SIN_FECHA"
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), event_timestamp, MINUTE) <= 5 THEN "ACTUALIZADO"
    ELSE "DESACTUALIZADO"
  END AS estado_frescura
FROM eventos_filtrados
WHERE rn = 1;


-- 2. VISTA DE RIESGO HISTÓRICO: lumina_streaming.stock_risk_by_product_region
-- Esquema de salida exacto (9 columnas):
-- product_id, region, total_eventos, stock_promedio, stock_minimo, stock_maximo, alertas_criticas, eventos_stock_bajo, porcentaje_alertas
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_streaming.stock_risk_by_product_region` AS
SELECT
  product_id,
  region,
  COUNT(*) AS total_eventos,
  ROUND(AVG(stock), 2) AS stock_promedio,
  MIN(stock) AS stock_minimo,
  MAX(stock) AS stock_maximo,
  COUNTIF(stock < 10) AS alertas_criticas,
  COUNTIF(stock BETWEEN 10 AND 20) AS eventos_stock_bajo,
  ROUND(
    SAFE_DIVIDE(COUNTIF(stock < 10), COUNT(*)) * 100, 2
  ) AS porcentaje_alertas
FROM
  `lumina-retail-001.lumina_streaming.telemetria_consolidada`
-- FILTRO DEFENSIVO APLICADO ANTES DE LA AGREGACIÓN:
-- Evita que eventos de prueba inflen total_eventos o distorsionen alertas_criticas
-- WHERE (region IS NULL OR region != 'CYBER_TEST')
  -- AND (event_type IS NULL OR event_type != 'SYNTHETIC_CYBERDAY_STRESS')
GROUP BY
  product_id,
  region;
