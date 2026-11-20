-- ==============================================================================
-- PROYECTO: LUMINA RETAIL — CICLO DE PEDIDOS EN STREAMING (CYBER DAYS)
-- DATASET: lumina_streaming
-- DESCRIPCIÓN: Definición de tabla externa sobre Parquet de órdenes y
--              vistas analíticas con balance de inventario y latencias P50..P99.
-- ==============================================================================

-- 1. TABLA EXTERNA: lumina_streaming.orders_stream_events
-- Conecta directamente con los micro-lotes Parquet generados por Spark Structured Streaming en GCS
CREATE OR REPLACE EXTERNAL TABLE `lumina-retail-001.lumina_streaming.orders_stream_events` (
  run_id STRING,
  event_id STRING,
  order_id STRING,
  event_type STRING,
  product_id STRING,
  region STRING,
  quantity INT64,
  unit_price FLOAT64,
  total_amount FLOAT64,
  stock_before INT64,
  stock_after INT64,
  order_status STRING,
  reason STRING,
  low_stock_alert BOOL,
  synthetic_flag BOOL,
  t_order_created FLOAT64,
  t_event_published FLOAT64,
  t_event_consumed FLOAT64,
  t_processing_started FLOAT64,
  t_processing_completed FLOAT64,
  t_inventory_updated FLOAT64,
  t_persisted FLOAT64,
  latency_publication_ms FLOAT64,
  latency_queue_ms FLOAT64,
  latency_processing_ms FLOAT64,
  latency_persistence_ms FLOAT64,
  latency_e2e_ms FLOAT64,
  processed_at TIMESTAMP
)
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://lumina-retail-001-data/gold/streaming/orders_v1/*.parquet']
);

-- 2. VISTA ANALÍTICA DE KPI Y OBSERVABILIDAD: lumina_streaming.orders_stream_summary_vw
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_streaming.orders_stream_summary_vw` AS
SELECT
  run_id,
  COUNT(*) AS total_eventos,
  COUNT(DISTINCT order_id) AS total_pedidos_unicos,
  COUNTIF(order_status = 'APPROVED') AS pedidos_aprobados,
  COUNTIF(order_status = 'REJECTED') AS pedidos_rechazados,
  COUNTIF(order_status = 'DUPLICATE_IGNORED') AS duplicados_neutralizados,
  ROUND(SAFE_DIVIDE(COUNTIF(order_status = 'APPROVED'), COUNT(*)) * 100, 2) AS tasa_aprobacion_pct,
  -- Métricas de Latencia End-to-End
  ROUND(AVG(latency_e2e_ms), 2) AS avg_latencia_e2e_ms,
  APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(50)] AS p50_latencia_e2e_ms,
  APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(90)] AS p90_latencia_e2e_ms,
  APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(95)] AS p95_latencia_e2e_ms,
  APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(99)] AS p99_latencia_e2e_ms,
  -- Métricas de Latencia de Publicación Kafka
  ROUND(AVG(latency_publication_ms), 2) AS avg_latencia_publicacion_ms,
  APPROX_QUANTILES(latency_publication_ms, 100)[OFFSET(95)] AS p95_latencia_publicacion_ms,
  -- Métricas de Latencia de Procesamiento Spark
  ROUND(AVG(latency_processing_ms), 2) AS avg_latencia_proceso_ms,
  APPROX_QUANTILES(latency_processing_ms, 100)[OFFSET(95)] AS p95_latencia_proceso_ms,
  -- Fechas de ejecución
  MIN(processed_at) AS inicio_procesamiento,
  MAX(processed_at) AS fin_procesamiento
FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
GROUP BY run_id;

-- 3. VISTA DE ESTADO DE INVENTARIO SINTÉTICO EN TIEMPO REAL: lumina_streaming.orders_inventory_state_vw
CREATE OR REPLACE VIEW `lumina-retail-001.lumina_streaming.orders_inventory_state_vw` AS
WITH ultimos_eventos AS (
  SELECT
    product_id,
    stock_after AS stock_actual,
    low_stock_alert,
    processed_at,
    ROW_NUMBER() OVER (
      PARTITION BY product_id
      ORDER BY processed_at DESC, event_id DESC
    ) AS rn
  FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
  WHERE order_status = 'APPROVED'
)
SELECT
  product_id,
  stock_actual,
  low_stock_alert,
  processed_at AS ultima_actualizacion
FROM ultimos_eventos
WHERE rn = 1;
