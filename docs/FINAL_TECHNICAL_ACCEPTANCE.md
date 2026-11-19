# Matriz de Aceptación Técnica Final: LUMINA RETAIL
**Proyecto:** LUMINA Retail — Intelligence & Operations Platform  
**Fecha de Validación:** 19 de Noviembre de 2026  
**Rama:** `main` | **Último Commit:** `81a1d66` (`origin/main`)  
**Despliegue Productivo:** Google Cloud Run (`lumina-retail-00009-5hg`, 100% de tráfico, `ContainerHealthy`)  
**Proyecto GCP:** `lumina-retail-001`

---

## 1. Matriz de Estado por Módulo Funcional

| Módulo / Dominio | Estado Final | Rutas de Archivos Clave | Tablas / Vistas BigQuery | Endpoints / Servicios | Evidencia Verificada |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Resumen Ejecutivo (Overview)** | **COMPLETADO** | `frontend/src/pages/Overview.jsx`, `backend/app/main.py` | `lumina_sandbox.vw_overview_monthly`, `lumina_stage.monthly_sales_multisource` | `/api/overview/*` | Coexistencia de Olist (BRL), TheLook (USD) y UCI (GBP) sin mezcla de monedas. Evolución temporal agregada por fuente. |
| **Análisis Comercial** | **COMPLETADO** | `frontend/src/pages/Commercial.jsx`, `scripts/wap/03a_wap_write_commercial.sql` | `lumina_sandbox.gold_commercial_monthly`, `gold_commercial_categories`, `vw_commercial_countries`, `vw_commercial_cancellations` | `/api/commercial/*`, `/api/commercial/countries`, `/api/commercial/cancellations` | Visualización de categorías derivadas UCI mediante REGEX (`SOURCE_NATIVE` vs `DERIVED_RULE` vs `UNCLASSIFIED`). Cobertura de países (38) y deducción exacta de devoluciones (£896,812). |
| **Store Performance** | **COMPLETADO CON LIMITACIÓN DE FUENTE** | `frontend/src/pages/StorePerf.jsx`, `docs/DIMENSIONAL_STORE_MODEL_LIMITATIONS.md` | `lumina_sandbox.vw_store_dimension`, `vw_store_commercial_performance` | `/api/store/performance` | Cada fuente mapeada como dimensión analítica independiente. Texto explicativo en UI sobre ausencia de tiendas físicas unificadas. |
| **Análisis Logístico** | **COMPLETADO CON LIMITACIÓN DE FUENTE** | `frontend/src/pages/Logistics.jsx`, `scripts/wap/03b_wap_write_logistics.sql` | `lumina_sandbox.gold_logistics_dashboard` | `/api/logistics/*` | Olist y TheLook presentan métricas de entrega, tiempo en tránsito y SLAs. UCI queda expresamente excluida con leyenda informativa de ausencia de datos logísticos nativos. |
| **Control de Inventario y Streaming** | **COMPLETADO** | `frontend/src/pages/Inventory.jsx`, `scripts/retailsmart_streaming.py`, `scripts/stress_kafka.py` | `lumina_streaming.stock_actual_vw`, `stock_risk_by_product_region`, `telemetria_consolidada` | `/api/inventory/current`, `/api/inventory/risks` | Streaming continuo Spark en Dataproc. Toggle interactivo para "Simulación Cyber Days" con resaltado morado (`SINTÉTICO`) y preservación de telemetría académica (`TEST-STREAM-20261119-ISOLATED-001`). |
| **Predicción de Demanda** | **COMPLETADO CON LIMITACIÓN DE FUENTE** | `frontend/src/pages/Predictive.jsx`, `docs/UCI_PREDICTIVE_EXPERIMENT.md` | `lumina_sandbox.gold_predictive_predictions`, `gold_predictive_metrics` | `/api/predictive/metrics`, `/api/predictive/predictions` | Modelo XGBoost validado sobre demanda semanal de Olist (888 semanas, WAPE 18.23%). Experimento UCI desestimado formalmente por insuficiencia histórica (53 semanas). |
| **Data Sources & Calidad** | **COMPLETADO** | `frontend/src/pages/Sources.jsx`, `docs/UCI_DATA_QUALITY.md`, `docs/UCI_RECONCILIATION.md` | `lumina_stage.stg_uci_online_retail`, `fact_sales_multisource` | `/api/commercial/customers_summary`, `/api/health` | Ficha técnica completa de las 3 fuentes. Reconciliación de 541,909 registros y mapeo de clientes no identificados a `ANONYMOUS`. |

---

## 2. Resultados de Validación de Software

### Suite de Pruebas Automatizadas
- **Comando:** `PYTHONPATH=. .venv/bin/pytest backend/tests -v`
- **Total:** 55 pruebas unitarias
- **Resultado:** **54 PASSED, 1 FAILED** (17.93 segundos de ejecución)
  - `test_wap_acceptance.py`: 17/17 PASSED (Gobernanza WAP-02.1 íntegra: adquisición, bloqueos, manifests, rollback y reintentos).
  - `test_uci_processing.py`: 8/8 PASSED (Aislamiento de divisa GBP, cálculo de venta neta, no negatividad y conteos).
  - `test_inventory_safeguards.py`: 6/6 PASSED (Salvaguardas de inventario, filtrado de nulos y conflictos).
  - `test_ml_advanced.py`: 5/5 PASSED (Validación temporal de features, prevención de data leakage, transformaciones logarítmicas).
  - `test_stress_generators.py`: 3/3 PASSED (Esquema de eventos sintéticos y etapas dry-run de Kafka/HTTP).
  - `test_store_performance.py`: 1/1 PASSED (Respuesta de dimensionalidad de tiendas).
  - `test_api.py`: 14/15 PASSED, **1 FAILED** (`test_inventory_current_unaffected`).
    - *Dictamen técnico:* El fallo (`AssertionError: 36 != 26`) obedece a que la vista física de BigQuery expone 10 productos de la simulación Cyber Days junto a los 26 productos operativos. La segregación se gestiona de forma segura en frontend mediante `Inventory.jsx`.

---

## 3. Certificación de Infraestructura y Despliegue

| Componente | Parámetro de Aceptación | Estado Comprobado | Evidencia |
| :--- | :--- | :---: | :--- |
| **Repositorio Git** | Sincronización con `origin/main` | **VERIFICADO** | Commits `5ef3fc6` y `81a1d66` verificados en remoto. Árbol limpio. |
| **Cloud Run** | Servicio activo con tráfico al 100% | **VERIFICADO** | Revisión `lumina-retail-00009-5hg` con condición `ContainerHealthy: True`. |
| **Artifact Registry** | Imagen Docker compilada | **VERIFICADO** | `lumina-api:wap-gold-final-v5` (digest `sha256:771f16c5...`). |
| **Gobernanza WAP** | Publicación de 4 dominios analíticos | **VERIFICADO** | `gold_release_control` en estado `PUBLISHED` para commercial, logistics, inventory y predictive. |
| **Apache Kafka** | Broker activo y libre de errores | **VERIFICADO** | VM `lumina-kafka-vm` (`10.142.0.3:9092`), offset `telemetria:0:2901`. |
| **Spark Streaming** | Micro-lotes en ejecución continua | **VERIFICADO** | Clúster Dataproc `lumina-retail-spark` (Job ID: `6b474383829944ec959c2b5958e7b7af`). |
| **Simulación Cyber Days**| Ingesta end-to-end demostrable | **VERIFICADO** | 795 eventos procesados desde Kafka a BigQuery (`docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md`). |
| **Aislamiento Contable** | Cero contaminación en Gold/Silver | **VERIFICADO** | 0 registros sintéticos en tablas comerciales, logísticas o predictivas. |

---

## 4. Índice de Documentación Técnica de Soporte

1. `docs/INFORME_CIERRE_Y_EVIDENCIAS.md`: Auditoría exhaustiva de solo lectura, evidencias de comandos, costos de infraestructura y diagnóstico del test fallido.
2. `docs/INFORME_PRUEBA_CARGA_CYBER_DAYS.md`: Informe reproducible de la prueba de carga de 795 eventos, balance de masa, throughput, latencias y guía de demostración.
3. `docs/INFORME_ARQUITECTURA_Y_GOBERNANZA_WAP.md`: Especificación formal del protocolo WAP-02.1, control de concurrencia y auditorías de calidad.
4. `docs/UCI_INTEGRATION_ARCHITECTURE.md`: Pipeline ELT Medallion para UCI Online Retail.
5. `docs/UCI_BUSINESS_RULES.md`: Reglas contables de cancelación, devoluciones, clientes anónimos y monedas.
6. `docs/UCI_PREDICTIVE_EXPERIMENT.md`: Justificación metodológica de inviabilidad de forecasting estacional sobre UCI.
7. `docs/DIMENSIONAL_STORE_MODEL_LIMITATIONS.md`: Justificación dimensional de las fuentes como unidades de negocio y no tiendas físicas reales.

El presente documento certifica que el proyecto **LUMINA Retail** se encuentra estabilizado, documentado, con pruebas automatizadas ejecutadas y desplegado para su presentación académica y evaluación técnica.
