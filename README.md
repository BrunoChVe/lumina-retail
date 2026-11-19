# LUMINA Retail — Intelligence & Operations Platform

Plataforma empresarial de analítica comercial, logística, predictiva y telemetría de inventarios multisource en la nube, diseñada bajo arquitectura Medallion, streaming reactivo y gobernanza estricta Write-Audit-Publish (WAP).

---

## 1. Arquitectura General y Tecnologías

```
[ Fuentes Multisource ]
  ├── Olist (eCommerce Brasil, Moneda: BRL)
  ├── TheLook (eCommerce Global, Moneda: USD)
  └── UCI Online Retail (Retail UK / Europa, Moneda: GBP)
       │
       ▼ (ELT Batch / PySpark / BigQuery SQL)
[ Data Lake & Data Warehouse ]
  ├── Google Cloud Storage (Bronze / Silver / Streaming Parquet)
  └── Google BigQuery (Esquemas: lumina_stage, lumina_sandbox, lumina_streaming)
       │
       ▼ (Gobernanza WAP-02.1: Write -> Audit -> Publish)
[ Capa Gold de Datos y Modelos ML ]
  ├── 4 Dominios Analíticos: Commercial, Logistics, Inventory, Predictive (XGBoost)
  └── Vistas Materializadas Segregadas por Moneda
       │
       ▼ (HTTP REST API / JSON)
[ Backend FastAPI ]
  ├── FastAPI en Python 3.12 (uvicorn)
  └── Desplegado en Google Cloud Run (Revisión: lumina-retail-00009-5hg, 100% tráfico)
       │
       ▼ (SPA Frontend / React 19 / Vite)
[ Frontend Web ]
  └── 7 Módulos: Overview, Commercial, Store Performance, Logistics, Inventory, Predictive, Sources
```

### Stack Tecnológico
| Capa | Tecnologías | Propósito |
|---|---|---|
| **Frontend** | React 19, Vite, Recharts, Lucide Icons | Dashboard interactivo y visualización analítica |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic | Exposición REST, validación WAP y control de acceso |
| **Data Warehouse** | Google BigQuery | Almacenamiento columnar analítico, particionamiento y clustering |
| **Data Lake** | Google Cloud Storage (GCS) | Ingesta cruda, snapshots y archivos Parquet de streaming |
| **Streaming Engine** | Apache Spark 3.5, Dataproc | Procesamiento continuo de telemetría de stock en micro-lotes de 5s |
| **Message Broker** | Apache Kafka 4.3 (Compute Engine) | Desacoplamiento de eventos de stock y simulación de carga |
| **Machine Learning** | XGBoost, Scikit-learn, Pandas | Modelado supervisado de demanda semanal con validación temporal |
| **Despliegue & Cloud** | Google Cloud Run, Cloud Build, Artifact Registry | Contenedores serverless protegidos por Identity-Aware Proxy (IAP) |

---

## 2. Fuentes de Datos y Aislamiento de Divisas

LUMINA Retail integra tres fuentes transaccionales heterogéneas preservando su semántica nativa:

1. **Olist (Brasil):** 
   - Operaciones de marketplace brasileño (2016–2018).
   - Moneda: **BRL** (Real brasileño).
   - Cobertura completa: comercial, logística detallada (fechas de entrega, SLAs, transportistas) y demanda semanal.
2. **TheLook eCommerce (Global):**
   - Transacciones sintéticas/públicas internacionales.
   - Moneda: **USD** (Dólar estadounidense).
   - Cobertura: comercial, catálogo y eventos logísticos generales.
3. **UCI Online Retail (Reino Unido / Europa):**
   - Transacciones minoristas transaccionales (Dic-2010 a Dic-2011).
   - Moneda: **GBP** (Libra esterlina).
   - Volumen: 541,909 registros brutos, ~£10.64 millones en ventas brutas, £896,812 en cancelaciones/devoluciones y 38 países.
   - Taxonomía: Derivada mediante expresiones regulares (`DERIVED_RULE` / `UNCLASSIFIED`).
   - Limitaciones: No dispone de campos nativos de despacho, transporte o SLAs logísticos; se excluye expresamente de métricas logísticas para evitar invención de datos.

> **Regla de Negocio (Monedas):** Las divisas **BRL**, **USD** y **GBP** se mantienen estrictamente aisladas en todas las tablas, vistas y tarjetas de KPI. No se efectúa consolidación aritmética multidivisa sin política de tipo de cambio histórico formal.

---

## 3. Protocolo de Gobernanza WAP-02.1 (Write-Audit-Publish)

La publicación hacia la capa Gold en BigQuery (`lumina_sandbox`) está gobernada por el protocolo WAP-02.1 implementado en SQL transaccional:

1. **Write:** Materialización de resultados analíticos bajo un identificador único de ejecución (`run_id`) y cálculo de *fingerprints* criptográficos.
2. **Audit:** 16 auditorías automatizadas (integridad referencial, conteo de filas, no negatividad de ventas, unicidad de llaves y consistencia temporal).
3. **Publish:** Si el 100% de las auditorías son aprobadas, se actualiza atómicamente la tabla `lumina_sandbox.gold_release_control`, transfiriendo el puntero productivo de forma idempotente.
4. **Rollback:** El script `scripts/wap/06_wap_rollback.sql` permite restituir la versión anterior inmediatamente ante cualquier anomalía.

**Estado Actual de Publicación en BigQuery:**
- Dominio **`commercial`**: `run_commercial_20261119085528_c222ee` (**PUBLISHED**)
- Dominio **`logistics`**: `run_logistics_20261119061637_0af4ef` (**PUBLISHED**)
- Dominio **`inventory`**: `run_inventory_20261119073856_f3a377` (**PUBLISHED**)
- Dominio **`predictive`**: `run_predictive_20261119083122_8b5685` (**PUBLISHED**)

---

## 4. Pipeline de Streaming y Simulación Cyber Days

### Arquitectura de Telemetría en Tiempo Real
```
[ Productor / Eventos Stock ] ──► [ Kafka Broker: telemetria ]
                                         │
                                         ▼ (Micro-batches: 5s)
                                 [ Dataproc Spark Streaming ]
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
             [ GCS Data Lake Parquet ]         [ GCS Checkpoints ]
                        │
                        ▼ (External Table)
             [ BigQuery: telemetria_consolidada ]
                        │
                        ▼ (Deduplicación ROW_NUMBER() = 1)
             [ BigQuery: stock_actual_vw ]
                        │
                        ▼
             [ FastAPI Backend (/api/inventory/*) ]
                        │
                        ▼
             [ Frontend React: Switch 'Simulación Cyber Days' ]
```

### Resultados de la Simulación Cyber Days (795 Eventos)
Se ejecutó un escenario de estrés con ráfagas controladas (10, 20 y 50 msgs/s) mediante `scripts/stress_kafka.py`:
- **Mensajes Inyectados y Confirmados:** **795 eventos** en 30 segundos (offset Kafka: 2106 → 2901).
- **Procesamiento Spark:** 7 micro-lotes absorbidos (Batches 20 al 26) sin fallos; throughput medio de **26.5 eventos/s** y pico de **49.6 eventos/s**.
- **Reconciliación en BigQuery:** 795 eventos verificados unívocamente por timestamp en `lumina_streaming.telemetria_consolidada`.
- **Segregación:** 0% de contaminación en tablas comerciales/logísticas. En el frontend, el control interactivo permite aislar o visualizar los 10 SKUs sintéticos destacados con la etiqueta `SINTÉTICO`.
- **Documento Completo:** Consulte [`docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md`](docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md).

---

## 5. Modelado Predictivo de Demanda (Machine Learning)

Se evaluó la demanda semanal agregada por categoría para Olist (panel de 103 semanas, 74 categorías):
- **Ventana de Prueba (Backtest):** Últimas 12 semanas disponibles (**888 observaciones**).
- **Modelos Evaluados:**
  - **Naive ($t-1$):** Persistencia simple ($\hat{y}_{c,t} = y_{c,t-1}$).
  - **XGBoost Regressor:** Modelo supervisado experimental con 11 variables de rezago, medias móviles y estacionalidad.
  - **Seasonal Naive ($t-52$):** Persistencia interanual.

### Benchmark Comparativo (888 Observaciones)
| Modelo | Tipo | MAE | RMSE | WAPE | Estado |
|---|---|---:|---:|---:|:---:|
| **Naive Baseline ($t-1$)** | Heurístico | **7.54** | **15.90** | **35.49%** | Benchmark de Referencia |
| **XGBoost (Experimental)** | Supervisado | 7.78 | 16.72 | 36.60% | Modelo Experimental Activo |
| **Seasonal Naive ($t-52$)** | Estacional | 12.79 | 27.18 | 60.21% | Subestimación por Crecimiento Anual |

> **Evaluación Predictiva en UCI:** Se documentó formalmente la **inviabilidad metodológica** de entrenar un modelo estacional sobre UCI debido a que solo cuenta con 53 semanas de historia, lo que impide calcular lags anuales (`t-52`) y efectuar backtesting robusto sin overfitting o data leakage (Ver [`docs/UCI_PREDICTIVE_EXPERIMENT.md`](docs/UCI_PREDICTIVE_EXPERIMENT.md)).

---

## 6. Módulos del Frontend (React / Vite)

1. **Overview (Resumen Ejecutivo):** Coexistencia de las tres fuentes, volúmenes de pedidos, ventas en sus monedas originales y tendencias temporales.
2. **Commercial (Análisis Comercial):** Ventas mensuales, ranking de productos, desglose geográfico por país (38 países en UCI), clientes y participación por categoría con reglas REGEX.
3. **Store Performance:** Análisis dimensional por fuente y unidad de negocio; documentación explícita de la ausencia de tiendas físicas unificadas.
4. **Logistics (Logística y Entregas):** Rendimiento de despacho, entregas a tiempo y SLAs para Olist y TheLook. UCI se identifica expresamente como fuente sin métricas logísticas nativas.
5. **Inventory (Monitoreo de Stock):** Telemetría en tiempo real, frescura de datos, matriz de riesgo de desabastecimiento e interruptor interactivo para la simulación Cyber Days.
6. **Predictive (Predicción de Demanda):** Desempeño del modelo supervisado XGBoost frente a baseline Naive, métricas WAPE/MAE/RMSE y curvas de error por categoría.
7. **Data Sources (Ficha Técnica y Gobernanza):** Catálogo de fuentes, cobertura temporal, volumen auditado, manejo de clientes anónimos y estado WAP.

---

## 7. Catálogo de Endpoints de la API REST (FastAPI)

| Método | Endpoint | Descripción | Dominio WAP / Fuente |
|:---:|---|---|:---:|
| `GET` | `/api/health` | Verificación de estado del backend y conexión BigQuery | General |
| `GET` | `/api/overview/metrics` | Indicadores consolidados por fuente de datos | General |
| `GET` | `/api/overview/monthly` | Evolución temporal de pedidos por fuente | General |
| `GET` | `/api/commercial/summary` | Resumen de ventas, tickets y órdenes | Commercial |
| `GET` | `/api/commercial/monthly` | Ventas mensuales agregadas por moneda | Commercial |
| `GET` | `/api/commercial/categories` | Ventas y participación por categoría | Commercial |
| `GET` | `/api/commercial/products` | Top productos y precios promedio | Commercial |
| `GET` | `/api/commercial/countries` | Ventas y órdenes por país (incluye 38 países de UCI) | Commercial |
| `GET` | `/api/commercial/customers_summary` | Clientes identificados vs. anónimos y ticket medio | Commercial |
| `GET` | `/api/commercial/cancellations` | Cancelaciones y ajustes contables por fuente | Commercial |
| `GET` | `/api/store/performance` | Desempeño dimensional por contexto comercial | Store Performance |
| `GET` | `/api/logistics/summary` | Resumen de entregas, fletes y tiempos en tránsito | Logistics |
| `GET` | `/api/logistics/monthly` | Evolución de actividad y entregas mensuales | Logistics |
| `GET` | `/api/inventory/current` | Snapshot de stock actual y estado de frescura | Inventory |
| `GET` | `/api/inventory/risks` | Histórico de alertas y riesgo por producto/región | Inventory |
| `GET` | `/api/predictive/metrics` | Métricas de evaluación de modelos (XGBoost vs. Naive) | Predictive |
| `GET` | `/api/predictive/predictions` | Predicciones de demanda semanal por categoría | Predictive |

---

## 8. Guía de Ejecución Local y Pruebas

### Requisitos Previos
- Python 3.12+ y `pip`
- Node.js 20+ y `npm`
- Google Cloud SDK (`gcloud`) autenticado con acceso al proyecto `lumina-retail-001`

### 1. Backend FastAPI
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
uvicorn app.main:app --reload --port 8080
```

### 2. Frontend React / Vite
```bash
cd frontend
npm ci
npm run dev
```
La aplicación estará disponible en `http://localhost:5173`. Vite redirige automáticamente las peticiones `/api/*` al backend local en el puerto 8080.

### 3. Ejecución de la Suite de Pruebas
```bash
# Desde la raíz del repositorio:
PYTHONPATH=. .venv/bin/pytest backend/tests -v
```
*Resultado auditado:* **54 pruebas aprobadas, 1 fallo documentado** (`test_inventory_current_unaffected` por coexistencia controlada de registros de Cyber Days).

---

## 9. Construcción Docker y Despliegue en Cloud Run

El repositorio incluye un `Dockerfile` multietapa optimizado:
1. **Etapa 1:** Compilación del frontend React Vite (`node:22-slim`).
2. **Etapa 2:** Runtime liviano de FastAPI (`python:3.12-slim`), empaquetando los estáticos compilados en `/frontend/dist`.

### Compilación y Despliegue en Google Cloud
```bash
# 1. Compilación distribuida en Cloud Build hacia Artifact Registry:
gcloud builds submit --tag us-central1-docker.pkg.dev/lumina-retail-001/lumina-retail/lumina-api:wap-gold-final-v5 .

# 2. Despliegue serverless en Cloud Run:
gcloud run deploy lumina-retail \
  --image us-central1-docker.pkg.dev/lumina-retail-001/lumina-retail/lumina-api:wap-gold-final-v5 \
  --region us-central1 \
  --allow-unauthenticated \
  --project lumina-retail-001

# 3. Asignación del 100% de tráfico a la última revisión:
gcloud run services update-traffic lumina-retail --to-latest --region us-central1 --project lumina-retail-001
```

**Estado Actual del Despliegue Productivo:**
- **Servicio:** `lumina-retail` (Región: `us-central1`).
- **Revisión Activa:** `lumina-retail-00009-5hg` (100% de tráfico, `ContainerHealthy: True`).
- **URL Productiva:** `https://lumina-retail-sv5avv2ypq-uc.a.run.app`.

---

## 10. Índice de Documentación Técnica

| Documento | Descripción |
|---|---|
| [`docs/INFORME_CIERRE_Y_EVIDENCIAS.md`](docs/INFORME_CIERRE_Y_EVIDENCIAS.md) | Informe formal de auditoría de solo lectura, evidencias de comandos, costos de infraestructura y diagnóstico de tests. |
| [`docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md`](docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md) | Memoria técnica reproducible de la simulación Cyber Days (795 eventos), balance de masa, métricas y guía de demostración. |
| [`docs/GRANULARIDAD_PREDICTIVA_Y_FILTROS.md`](docs/GRANULARIDAD_PREDICTIVA_Y_FILTROS.md) | Auditoría de granularidad dimensional por fuente, pronósticos por tienda/vendedor/producto y criterio de suficiencia de historial. |
| [`docs/INVENTARIO_ANALITICO_UCI.md`](docs/INVENTARIO_ANALITICO_UCI.md) | Modelo y endpoints del inventario analítico y demanda histórica para la fuente UCI Online Retail. |
| [`docs/ARQUITECTURA_PEDIDOS_CYBER_DAYS.md`](docs/ARQUITECTURA_PEDIDOS_CYBER_DAYS.md) | Arquitectura implementada para streaming y propuesta de diseño para el ciclo de pedidos transaccional. |
| [`docs/FINAL_TECHNICAL_ACCEPTANCE.md`](docs/FINAL_TECHNICAL_ACCEPTANCE.md) | Matriz de aceptación técnica por módulo, componentes validados y estado de certificación. |
| [`docs/INFORME_ARQUITECTURA_Y_GOBERNANZA_WAP.md`](docs/INFORME_ARQUITECTURA_Y_GOBERNANZA_WAP.md) | Especificación formal del protocolo WAP-02.1, control de concurrencia y auditorías SQL. |
| [`docs/UCI_INTEGRATION_ARCHITECTURE.md`](docs/UCI_INTEGRATION_ARCHITECTURE.md) | Arquitectura ELT Medallion para la ingesta de UCI Online Retail. |
| [`docs/UCI_BUSINESS_RULES.md`](docs/UCI_BUSINESS_RULES.md) | Reglas contables de cancelaciones, devoluciones y manejo de clientes anónimos. |
| [`docs/UCI_PREDICTIVE_EXPERIMENT.md`](docs/UCI_PREDICTIVE_EXPERIMENT.md) | Justificación metodológica de inviabilidad de forecasting estacional sobre UCI. |
| [`docs/DIMENSIONAL_STORE_MODEL_LIMITATIONS.md`](docs/DIMENSIONAL_STORE_MODEL_LIMITATIONS.md) | Justificación técnica del modelado dimensional de fuentes versus tiendas físicas. |
| [`docs/UCI_DATA_QUALITY.md`](docs/UCI_DATA_QUALITY.md) | Perfilado de calidad, nulos y limpieza de datos en UCI Online Retail. |
| [`docs/UCI_RECONCILIATION.md`](docs/UCI_RECONCILIATION.md) | Reconciliación matemática entre registros Bronze y vistas Gold de UCI. |

---

**LUMINA Retail** — *Enterprise Intelligence & Operations Platform (2026)*.
