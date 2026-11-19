-- SCRIPT 07: ESTRATEGIA DE FINGERPRINTS DETERMINISTAS
-- Define formalmente los tres niveles de huellas, sus dependencias exactas y sus limitaciones documentadas.

-- =============================================================================
-- 1. FINGERPRINT_LOGIC (Identidad del Código de Transformación)
-- =============================================================================
-- Alcance: Inyectado por el pipeline de CI/CD / Orquestador.
-- Cálculo: SHA256(git_commit_sha + ":" + catalog_version + ":" + sql_source_hash)
-- Qué detecta: Cualquier cambio en los scripts DDL/DML, código Python o catálogo de reglas.
-- Qué NO detecta: Modificaciones en los datos de entrada cuando el código es idéntico.

-- =============================================================================
-- 2. FINGERPRINT_METADATA (Identidad del Catálogo Físico en BigQuery)
-- =============================================================================
-- Alcance: Dependencias físicas en lumina_stage (fact_sales_multisource, stg_uci_online_retail).
SELECT TO_JSON_STRING(ARRAY(
  SELECT STRUCT(
    table_id, 
    row_count, 
    last_modified_time
  ) 
  FROM `lumina-retail-001.lumina_stage.__TABLES__` 
  WHERE table_id IN ("fact_sales_multisource", "stg_uci_online_retail")
  ORDER BY table_id
)) AS fingerprint_metadata;
-- Qué detecta: Inserciones, truncados o cargas masivas que alteren row_count o last_modified_time.
-- Qué NO detecta: Mutaciones internas revertidas mediante Time Travel, actualizaciones simétricas
--                 que preserven el row_count exacto, o cambios en vistas no materializadas.

-- =============================================================================
-- 3. FINGERPRINT_OPERATIONAL (Huella Parcial y Muestreo de Contenido)
-- =============================================================================
-- Alcance: Subconjunto ordenado de campos deterministas en stg_uci_online_retail y fact_sales_multisource.
-- Se utiliza serialización estructurada con TO_JSON_STRING(STRUCT(...)) para evitar ambigüedades de CONCAT.
SELECT CAST(SUM(CAST(FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(
   source_order_id, 
   source_product_id, 
   quantity, 
   product_sales, 
   order_status
))) AS BIGNUMERIC)) AS STRING) AS fingerprint_operational_uci
FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail`;

-- LIMITACIONES TÉCNICAS Y RIESGOS DOCUMENTADOS:
-- 1. FARM_FINGERPRINT es una función hash de 64 bits de propósito general, NO es un hash criptográfico.
-- 2. Existe riesgo de colisión matemática de 64 bits.
-- 3. SUM(CAST(... AS BIGNUMERIC)) es conmutativo: no detecta si dos filas intercambian valores entre sí 
--    produciendo la misma suma acumulada, ni valida ordenamiento físico.
-- 4. No es una prueba absoluta de integridad de todo el Data Warehouse: es un estimador operacional
--    de bajo costo para evitar ejecuciones idénticas redundantes (Short-circuit).
-- 5. Para una garantía de integridad absoluta en producción, la arquitectura deberá incorporar en una fase
--    posterior manifiestos de ingesta persistidos y sellados durante la carga de Bronze/Silver.
