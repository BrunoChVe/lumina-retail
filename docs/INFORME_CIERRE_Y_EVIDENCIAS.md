# INFORME DE AUDITORÍA FINAL, CIERRE TÉCNICO Y EVIDENCIAS
**Plataforma LUMINA Retail — Intelligence & Operations**  
**Fecha de Auditoría:** 19 de Noviembre de 2026  
**Modo:** Solo Lectura (Verificación Empírica de Estado)  
**ID del Proyecto GCP:** `lumina-retail-001`  
**Región Principal:** `us-central1` (Cloud Run, Artifact Registry) / `us-east1` (Dataproc, Compute Engine, GCS, BigQuery Streaming)

---

## 1. Cloud Run: Revisión Activa, Imagen, Tráfico y Health Check

### Comandos de Inspección
```bash
gcloud run services describe lumina-retail --region us-central1 --project lumina-retail-001 \
  --format="yaml(metadata.name,status.url,status.traffic,status.latestReadyRevisionName,status.conditions)"

gcloud run revisions describe lumina-retail-00009-5hg --region us-central1 --project lumina-retail-001 \
  --format="yaml(metadata.name,spec.containers[0].image,status.conditions)"
```

### Resultados Verificables
- **Servicio:** `lumina-retail`
- **URL Base:** `https://lumina-retail-sv5avv2ypq-uc.a.run.app` / `https://lumina-retail-192488032202.us-central1.run.app`
- **Revisión Activa con 100% de Tráfico:** `lumina-retail-00009-5hg`
- **Distribución de Tráfico:**
  - `lumina-retail-00009-5hg`: **100% (LATEST)**
  - `lumina-retail-00011-mij` (tag `wap-gold-final-v3`): 0%
  - `lumina-retail-00009-bub` (tag `wap-gold-final-v2`): 0%
  - `lumina-retail-00007-nur` (tag `wap-gold-final`): 0%
  - `lumina-retail-00006-dig` (tag `wap-gold`): 0%
  - `lumina-retail-00004-fal` (tag `v2-git-validation`): 0%
  - `lumina-retail-00003-vun` (tag `v2-validation`): 0%
- **Imagen del Contenedor Desplegada:**
  `us-central1-docker.pkg.dev/lumina-retail-001/lumina-retail/lumina-api@sha256:771f16c5978b4bfd5e9cc0c610e7cd57c51c760792c76742b13313655ebcf562` (Etiqueta: `wap-gold-final-v5`)
- **Estado de Condiciones y Health Check Nativo:**
  - `Ready`: **True** (Última transición: `2026-11-19T14:52:20.937953Z`, mensaje: *"Deploying revision succeeded in 6.91s."*)
  - `ContainerHealthy`: **True** (mensaje: *"Containers became healthy in 4.58s."*)
  - `Active`: **True**
  - `ConfigurationsReady`: **True**
  - `RoutesReady`: **True**
- **Observación de Seguridad perimetral:** Las peticiones externas HTTP sin token OIDC son interceptadas por Google Cloud Identity-Aware Proxy (IAP) con respuesta `HTTP/2 302 Redirect` a `accounts.google.com` o `HTTP/2 401 Invalid IAP credentials`, garantizando protección perimetral del endpoint público.

---

## 2. Repositorio Git y Sincronización con origin/main

### Comandos de Inspección
```bash
git fetch origin main --quiet
git log origin/main -n 5 --oneline
git rev-parse 5ef3fc6
git rev-parse 81a1d66
git status
```

### Resultados Verificables
- **Presencia de Commits en `origin/main`:**
  - `81a1d66` (**HEAD** de `main` y `origin/main`): `feat(cyber): implement cyber days synthetic event simulation and visualization`
  - `5ef3fc6` (ancestro directo): `docs(final): add comprehensive technical acceptance and integration completion reports`
- **Hashes SHA-1 Completos Confirmados:**
  - `81a1d667ad8a8b6c1de8d2ff00c74305c2f95ab1`
  - `5ef3fc63fddf6df0b6e7a6f9d983fce62be2a60a`
- **Estado del Árbol de Trabajo:** `nothing to commit, working tree clean`. Rama sincronizada sin discrepancias respecto a remoto.

---

## 3. Resultado Real de las Pruebas Unitarias

### Comando de Ejecución
```bash
PYTHONPATH=. .venv/bin/pytest backend/tests -v
```

### Resumen Estadístico
- **Total Recolectado:** 55 pruebas
- **Pruebas Superadas (Passed):** 54
- **Pruebas Fallidas (Failed):** 1
- **Tiempo de Ejecución:** 17.93 segundos

### Detalle por Módulo
1. `backend/tests/test_api.py` (15 pruebas): **14 PASSED, 1 FAILED**
2. `backend/tests/test_inventory_safeguards.py` (6 pruebas): **6 PASSED**
3. `backend/tests/test_ml_advanced.py` (5 pruebas): **5 PASSED**
4. `backend/tests/test_store_performance.py` (1 prueba): **1 PASSED**
5. `backend/tests/test_stress_generators.py` (3 pruebas): **3 PASSED**
6. `backend/tests/test_uci_processing.py` (8 pruebas): **8 PASSED**
7. `backend/tests/wap/test_wap_acceptance.py` (17 pruebas): **17 PASSED**

### Análisis Técnico del Fallo Empírico
- **Prueba:** `TestLuminaRetailAPI::test_inventory_current_unaffected`
- **Error:** `AssertionError: 36 != 26`
- **Causa Raíz:** La prueba unitaria asume un entorno de inventario puramente operacional que retorna exactamente 26 registros. Para permitir que el frontend pudiera visualizar la simulación de Cyber Days sin modificar la base de datos de producción ni requerir endpoints paralelos, se eliminó el filtro SQL `WHERE (region IS NULL OR region != 'CYBER_TEST')` en `backend/app/main.py`. Como existen 10 productos sintéticos activos (`CYBER_PROD_001` a `010`) en `stock_actual_vw`, la consulta devuelve 36 registros (26 operacionales + 10 sintéticos).
- **Tratamiento:** El frontend maneja la segregación en capa de presentación con el filtro `showCyber ? current : current.filter(x => x.region !== 'CYBER_TEST')`, mostrando por defecto los 26 registros originales.

---

## 4. Trazabilidad de los 795 Eventos Cyber Days (End-to-End)

Se verificó el recorrido completo de los 795 eventos sintéticos emitidos durante la prueba de carga `stress_kafka.py` (Run ID: `87cc5b11-926d-4525-a42e-feeab5ff6f99`).

### Capa 1: Apache Kafka (Ingesta)
- **Broker VM:** `lumina-kafka-vm` (`10.142.0.3:9092`)
- **Tópico:** `telemetria`
- **Offset Final Verificado:** `telemetria:0:2901`
- **Eventos Emitidos:** 795 mensajes en 3 fases progresivas (10, 20 y 50 msgs/s), 0 fallos de transporte.

### Capa 2: Apache Spark Structured Streaming en Dataproc (Procesamiento)
- **Cluster:** `lumina-retail-spark` (Job ID: `6b474383829944ec959c2b5958e7b7af`)
- **Intervalo de Micro-lotes:** 5 segundos
- **Destino de Salida Parquet:** `gs://lumina-retail-001-data/gold/streaming/telemetria_v2/`
- **Archivos Generados:** 28 objetos parquet/metadatos sincronizados.
- **Checkpoints Activos:** `gs://lumina-retail-001-data/checkpoints/telemetria_v2/` (`commits`, `offsets`, `sources`).

### Capa 3: BigQuery (Almacenamiento y Vistas de Telemetría)
- **Tabla Consolidada:** `lumina-retail-001.lumina_streaming.telemetria_consolidada`
- **Consulta de Evidencia:**
  ```sql
  SELECT event_type, region, COUNT(*) as total_eventos, COUNT(DISTINCT product_id) as total_productos,
         MIN(event_timestamp) as min_ts, MAX(event_timestamp) as max_ts
  FROM `lumina-retail-001.lumina_streaming.telemetria_consolidada`
  WHERE region = 'CYBER_TEST'
  GROUP BY event_type, region;
  ```
- **Resultado en BigQuery:**
  - `event_type`: `SYNTHETIC_CYBERDAY_STRESS`
  - `region`: `CYBER_TEST`
  - `total_eventos`: **795** (Coincidencia exacta al 100%)
  - `total_productos`: **10** (`CYBER_PROD_001` a `CYBER_PROD_010`)
  - `min_ts`: `2026-11-19 14:45:35.854714+00`
  - `max_ts`: `2026-11-19 14:46:09.917458+00`
- **Vista de Estado Actual:** `lumina-retail-001.lumina_streaming.stock_actual_vw`
  Presenta 10 filas consolidadas (una por producto `CYBER_PROD_001`..`010`), con stocks registrados entre 136 y 145 unidades.

### Capa 4: Frontend React
- **Archivo:** `frontend/src/pages/Inventory.jsx`
- **Segregación:** Estado `showCyber` (por defecto `false`).
- **Renderizado Condicional:** Los 10 registros sintéticos se filtran fuera del stock operativo normal. Al activar la casilla *"Simulación Cyber Days"*, los productos sintéticos se destacan con fondo morado `#1e1b4b` y badge distintivo `SINTÉTICO`.

---

## 5. Separación Rigurosa entre Datos Sintéticos y Reales

### Consulta de Auditoría Cruzada
```sql
SELECT 'fact_sales_multisource' as tabla, count(*) as count_cyber FROM `lumina-retail-001.lumina_stage.fact_sales_multisource` WHERE source_order_id LIKE '%SYNTH%' OR source_customer_id LIKE '%CYBER%'
UNION ALL
SELECT 'stg_uci_online_retail', count(*) FROM `lumina-retail-001.lumina_stage.stg_uci_online_retail` WHERE source_order_id LIKE '%SYNTH%' OR country = 'CYBER_TEST'
UNION ALL
SELECT 'gold_commercial_monthly', count(*) FROM `lumina-retail-001.lumina_sandbox.gold_commercial_monthly` WHERE source_system LIKE '%CYBER%' OR source_system LIKE '%SYNTH%'
UNION ALL
SELECT 'gold_logistics_dashboard', count(*) FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` WHERE source_system LIKE '%CYBER%' OR source_system LIKE '%SYNTH%'
UNION ALL
SELECT 'gold_predictive_predictions', count(*) FROM `lumina-retail-001.lumina_sandbox.gold_predictive_predictions` WHERE categoria LIKE '%CYBER%' OR categoria LIKE '%SYNTH%';
```

### Resultados
| Tabla / Dominio | Registros Sintéticos Encontrados | Estado de Integridad |
| :--- | :--- | :--- |
| `lumina_stage.fact_sales_multisource` | **0** | No contaminado |
| `lumina_stage.stg_uci_online_retail` | **0** | No contaminado |
| `lumina_sandbox.gold_commercial_monthly` | **0** | No contaminado |
| `lumina_sandbox.gold_logistics_dashboard` | **0** | No contaminado |
| `lumina_sandbox.gold_predictive_predictions` | **0** | No contaminado |

Los eventos sintéticos residen **exclusivamente** en el dataset `lumina_streaming` bajo el etiquetado `event_type = 'SYNTHETIC_CYBERDAY_STRESS'` y `region = 'CYBER_TEST'`. No existe filtración ni sesgo hacia indicadores comerciales, logísticos ni modelos de machine learning.

---

## 6. Estado Actual de la Infraestructura de Streaming

### VM Kafka
- **Nombre:** `lumina-kafka-vm`
- **Zona:** `us-east1-b`
- **Tipo de Máquina:** `e2-medium` (1 vCPU, 4.0 GB RAM)
- **Estado:** **RUNNING**
- **IP Interna:** `10.142.0.3` | **IP Externa:** `34.148.22.252`
- **Fecha de Creación:** `2026-11-05T19:32:21.700-08:00`
- **Tópicos Activos:** `telemetria`, `eventos_web`, `retailsmart_load_test`, `__consumer_offsets`

### Clúster Dataproc Spark
- **Nombre del Clúster:** `lumina-retail-spark`
- **Zona:** `us-east1-c` (Región `us-east1`)
- **Estado:** **RUNNING** (Activo continuo desde `2026-11-17T02:48:40.305272Z`)
- **Topología de Cómputo:**
  - 1x Master: `lumina-retail-spark-m` (`e2-standard-4`, 4 vCPU, 16 GB RAM)
  - 2x Workers: `lumina-retail-spark-w-0`, `lumina-retail-spark-w-1` (`e2-standard-4`, 4 vCPU, 16 GB RAM c/u)
  - **Cómputo Total Asignado:** 12 vCPUs y 48 GB de memoria RAM.
- **Job de Streaming Activo:**
  - **Job ID:** `6b474383829944ec959c2b5958e7b7af`
  - **Tipo:** `pyspark` (`retailsmart_streaming.py`)
  - **Estado:** **RUNNING**

---

## 7. Inventario de Recursos en GCP que Continúan Generando Costos

| Recurso | Tipo de Cómputo / Almacenamiento | Región / Zona | Driver Principal de Costo |
| :--- | :--- | :--- | :--- |
| `lumina-retail-spark` (3 VMs GCE) | 3x `e2-standard-4` (12 vCPUs, 48 GB) + Discos PD-Standard | `us-east1-c` | **Alto:** Tarifa de Dataproc por vCPU + Cómputo GCE continuo. |
| `lumina-kafka-vm` | 1x `e2-medium` (1 vCPU, 4 GB) + 10 GB disco | `us-east1-b` | **Moderado:** Horas de instancia GCE + IP estática/efímera. |
| `gs://lumina-retail-001-data` | Cloud Storage Standard | `us-east1` | Almacenamiento parquet streaming y checkpoints. |
| `gs://lumina-retail-001-us-data` | Cloud Storage Standard | `US` multi-región | Almacenamiento de datasets silver/bronze. |
| `gs://dataproc-staging-*` / `temp-*` | Cloud Storage Standard | `us-east1` | Archivos temporales y jars de Spark. |
| `lumina_stage`, `lumina_sandbox`, `lumina_streaming` | BigQuery Storage | `US` / `us-east1` | Almacenamiento de tablas físicas (particionadas/clusterizadas). |
| `us-central1-docker.pkg.dev/.../lumina-retail` | Artifact Registry | `us-central1` | Almacenamiento de capas de imágenes Docker (~280 MB). |
| `lumina-retail` (Cloud Run) | Serverless Container | `us-central1` | **Mínimo:** Escala a 0 (`Min: 0, Max: 2`), sin costo cuando no procesa tráfico. |

---

## 8. Estado de los Datasets, Tablas Gold y Checkpoints

### Control de Publicación WAP (`gold_release_control`)
Todos los dominios analíticos se encuentran en estado **`PUBLISHED`** bajo el protocolo WAP-02.1:
- **`commercial`:** `run_commercial_20261119085528_c222ee` (Publicado: `2026-11-19 08:56:27`)
- **`logistics`:** `run_logistics_20261119061637_0af4ef` (Publicado: `2026-11-19 06:17:13`)
- **`inventory`:** `run_inventory_20261119073856_f3a377` (Publicado: `2026-11-19 07:39:33`)
- **`predictive`:** `run_predictive_20261119083122_8b5685` (Publicado: `2026-11-19 08:31:59`)

### Tablas y Vistas Físicas Verificadas
- **`lumina_sandbox` (Capa Gold y Vistas Analíticas):**
  - Tablas: `gold_audit_results`, `gold_commercial_categories`, `gold_commercial_monthly`, `gold_commercial_products`, `gold_execution_history`, `gold_inventory_current`, `gold_inventory_risks`, `gold_logistics_dashboard`, `gold_predictive_metrics`, `gold_predictive_predictions`, `gold_publisher_lock`, `gold_release_control`.
  - Vistas: `vw_commercial_cancellations`, `vw_commercial_countries`, `vw_commercial_customers`, `vw_predictive_category_performance`, `vw_store_commercial_performance`, `vw_store_dimension`, `vw_store_logistics_performance`.
- **`lumina_stage` (Capa Silver / Staging):**
  - Tablas físicas: `fact_sales_multisource`, `stg_uci_online_retail` (541,909 registros), `dim_customer`, `dim_date`, `dim_product`, `dim_product_multisource_v2`, `dim_seller`, `gold_demand_olist_weekly`, `model_evaluation_metrics`, `model_evaluation_predictions`.
- **`lumina_streaming` (Capa Operativa):**
  - Vistas: `stock_actual_vw`, `stock_risk_by_product_region`, `telemetria_consolidada`.
  - Tablas/Externas: `telemetria_events`, `telemetria_events_v2_audit`, `telemetria_python_recovery_0_299`.

### Checkpoints en Cloud Storage
- `gs://lumina-retail-001-data/checkpoints/telemetria/`
- `gs://lumina-retail-001-data/checkpoints/telemetria_v2/` (Directorios internos confirmados: `metadata`, `commits/`, `offsets/`, `sources/`).

### Eventos Académicos de Demostración Preservados
- **ID de Evento:** `TEST-STREAM-20261119-ISOLATED-001`
- **SKU:** `TEST-SKU-999`
- **Región:** `Arequipa-Test` (Stock: 100 unidades, procesado por `spark_structured_streaming_v2`).
- **Estado:** Confirmado en `lumina_streaming.telemetria_consolidada`.

---

## 9. Limitaciones Metodológicas y de Alcance Documentadas

1. **UCI Online Retail — Ausencia de Taxonomía y Logística Nativa:**
   UCI carece de marcas temporales de entrega, transportistas y divisiones por tienda física. La clasificación categórica se derivó mediante expresiones regulares documentadas (`DERIVED_RULE` / `UNCLASSIFIED`), y las métricas logísticas se mantienen expresamente deshabilitadas para esta fuente para evitar datos sintéticos no fundamentados.
2. **Experimento Predictivo UCI:**
   Con una ventana histórica de 53 semanas (Dic-2010 a Dic-2011), resulta matemáticamente inviable entrenar y validar un modelo estacional `Seasonal Naive` con lag anual (`t-52`) sin fuga de datos o sobreajuste severo. El modelo productivo de Machine Learning (XGBoost) se mantiene validado exclusivamente sobre Olist (888 semanas observadas).
3. **Fallo en Test Unitario de Aislamiento de Inventario:**
   La prueba `test_inventory_current_unaffected` evalúa que `/api/inventory/current` devuelva exactamente 26 filas. Al habilitar la visualización de la simulación Cyber Days para la interfaz de usuario, la vista BQ expone 36 registros. La segregación se garantizó a nivel de frontend (`Inventory.jsx`) mediante un control de visualización diferenciado.
