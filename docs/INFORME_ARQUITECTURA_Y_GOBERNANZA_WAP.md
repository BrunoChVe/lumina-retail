# LUMINA Retail: Informe de Arquitectura, Gobernanza WAP y Evaluación Predictiva

**Proyecto:** LUMINA Retail (RetailSmart Data Platform)  
**Institución / Contexto:** Proyecto de Fin de Máster / Ingeniería de Datos en Cloud  
**Autor:** Bruno Chihuán Velásquez  
**Fecha:** Noviembre 2026  
**Entorno Cloud:** Google Cloud Platform (`lumina-retail-001`)  
**Revisión Productiva:** `wap-gold-final` (Cloud Run)  

---

## 1. Resumen Ejecutivo

LUMINA Retail es una plataforma integral de ingeniería de datos, analítica multisource y modelado predictivo diseñada para operar sobre infraestructuras cloud modernas bajo estrictos principios de gobernanza, integridad transaccional y disponibilidad continua.

El presente informe documenta la culminación de la fase Gold de la plataforma, caracterizada por la implementación del protocolo **Write-Audit-Publish (WAP-02.1)** con control de concurrencia optimista (OCC), *fencing tokens* monotónicos anti-zombie y *leasing* temporal. Asimismo, se expone la resolución técnica de la arquitectura híbrida de inventario en streaming que respeta las restricciones de ubicación regional entre `us-east1` y multirregión `US`, la migración y gobierno del pipeline de predicción de demanda mediante Machine Learning (XGBoost vs. Baselines), y la validación automatizada mediante una suite de 52 pruebas de software y aceptación formal.

---

## 2. Arquitectura Global de Datos

La plataforma sigue una arquitectura Medallion desacoplada y multicanal, integrando fuentes transaccionales heterogéneas tanto en modalidad batch como streaming:

```
[Fuentes Batch: Olist (BRL), TheLook (USD), UCI (GBP)]
           │
           ▼
[Bronze: Google Cloud Storage / Raw Ingestion]
           │ (Dataproc PySpark / SQL ETL)
           ▼
[Silver: Tablas y Vistas Limpias (lumina_stage)]
           │
           ▼  ◄─── [Protocolo Transaccional WAP-02.1 con OCC & Fencing Tokens]
[Gold: Sandboxes Auditados y Publicación Atómica (lumina_sandbox)]
           │
           ├─ Commercial (Monthly, Categories, Products)
           ├─ Logistics (Dashboard de Calidad y Tiempos)
           ├─ Inventory (Snapshots Auditados + Telemetría Viva)
           └─ Predictive (Métricas y Predicciones de Demanda)
           │
           ▼
[FastAPI Backend + React 19 SPA Frontend (Google Cloud Run)]
```

### 2.1. Fuentes de Datos y Aislamiento de Divisas
- **Olist Store:** E-commerce brasileño. Divisa documentada: Real Brasileño (**BRL**).
- **TheLook eCommerce:** E-commerce internacional sintético. Divisa confirmada: Dólar Estadounidense (**USD**).
- **UCI Online Retail:** Transacciones transfronterizas europeas y del Reino Unido. Divisa documentada: Libra Esterlina (**GBP**).

**Garantía de Aislamiento Monetario:** La arquitectura impone una separación estricta por fuente y divisa. Bajo ninguna circunstancia la capa de almacenamiento ni los endpoints analíticos agregan métricas monetarias de monedas distintas. Cada registro preserva su código ISO `currency_code` y su estado de validación `currency_status`.

---

## 3. Implementación del Protocolo Write-Audit-Publish (WAP-02.1)

Para evitar la polución de la capa analítica de producción ante anomalías de calidad, inconsistencias de clave primaria o transformaciones defectuosas, LUMINA Retail implementó el protocolo transaccional WAP a nivel de base de datos en BigQuery (`lumina_sandbox`).

### 3.1. Principios y Mecanismos de Control
1. **Adquisición Atómica con OCC (`02_wap_acquire.sql`):**
   - Utiliza la tabla `gold_publisher_lock`.
   - Implementa control de concurrencia optimista mediante transacciones BigQuery y renovación condicional de *lease* (vigencia de 30 minutos).
   - Genera un `fencing_token` monotónico incremental que invalida cualquier intento de publicación por parte de procesos lentos o desincronizados (*split-brain / zombie mitigation*).
2. **Escritura Aislada en Sandbox (`03a`-`03d`):**
   - Los datos transformados se insertan identificados por un `run_id` determinista o unívoco.
   - Cada inserción registra eventos auditables de secuencia y metadatos en `gold_execution_history`.
3. **Auditoría Exhaustiva Automatizada (`04a`-`04d`):**
   - Ejecución de aserciones de integridad relacional, no nulidad de PK, ausencia de datos sintéticos no productivos y validez lógica.
   - Los resultados se escriben en `gold_audit_results` con su versión de catálogo (`catalog_version`).
4. **Publicación Atómica y Validación Simétrica (`05_wap_publish.sql`):**
   - Comprueba mediante conjuntos relacionales (`EXCEPT DISTINCT`) que el catálogo de auditorías ejecutado coincida exactamente con la lista de pruebas obligatorias (`@mandatory_tests`), sin pruebas faltantes, inesperadas, duplicadas ni fallidas.
   - Verifica simétricamente el manifiesto de tablas generadas (`@mandatory_tables`).
   - Valida que el *lease* no haya expirado ni haya sido tomado por otro proceso (`fencing_token` consistente).
   - Actualiza atómicamente la tabla `gold_release_control` con el `current_run_id` y libera el *lock* en una única transacción ACID.
5. **Rollback Determinista (`06_wap_rollback.sql`):**
   - Permite restituir de forma instantánea la versión productiva anterior (`previous_run_id`) ante incidentes en producción sin necesidad de reconstruir las tablas desde cero.

### 3.2. Catálogo Oficial de Auditorías por Dominio

| Dominio | Código de Prueba | Condición Auditada | Estado en Producción |
|---|---|---|:---:|
| **Commercial** | `TEST_COMM_CURRENCY_ISOLATION` | Cero mezclas de moneda en agregaciones | **PASSED** |
| **Commercial** | `TEST_COMM_PK_MONTHLY_NOT_NULL` | Clave primaria mensual no nula | **PASSED** |
| **Commercial** | `TEST_COMM_MONTHLY_GRAIN_UNIQUENESS` | Unicidad estricta de grano mensual | **PASSED** |
| **Commercial** | `TEST_COMM_UCI_NO_INVENTED_CATEGORIES` | Categorías UCI consistentes sin invención | **PASSED** |
| **Commercial** | `TEST_COMM_UCI_GRANULARITY_AND_PRESERVATION` | Preservación de granularidad y totales UCI | **PASSED** |
| **Commercial** | `TEST_COMM_INTEGRITY_MONTHLY_VS_PRODUCTS` | Integridad referencial entre tablas comerciales | **PASSED** |
| **Logistics** | `TEST_LOG_UCI_EXCLUDED` | Exclusión rigurosa de UCI (sin datos logísticos) | **PASSED** |
| **Logistics** | `TEST_LOG_SOURCES_ALLOWED` | Fuentes permitidas restringidas a Olist y TheLook | **PASSED** |
| **Logistics** | `TEST_LOG_PK_NOT_NULL` | Clave primaria del dashboard logístico no nula | **PASSED** |
| **Logistics** | `TEST_LOG_UNIQUENESS` | Grano único por mes y fuente | **PASSED** |
| **Inventory** | `TEST_INV_PK_NOT_NULL` | Clave primaria (producto, región) no nula | **PASSED** |
| **Inventory** | `TEST_INV_NO_CYBER_TEST` | Exclusión de eventos de estrés `CYBER_TEST` | **PASSED** |
| **Inventory** | `TEST_INV_NO_NEGATIVE_STOCK` | Cero registros con stock negativo | **PASSED** |
| **Predictive** | `TEST_PRED_METRICS_EXIST` | Existencia de métricas de evaluación del modelo | **PASSED** |
| **Predictive** | `TEST_PRED_NO_NEGATIVE_PREDS` | Cero predicciones de demanda negativas | **PASSED** |
| **Predictive** | `TEST_PRED_VALID_DATES` | Fechas semanales válidas y no nulas | **PASSED** |

**Resultado consolidado:** 16 de 16 auditorías obligatorias aprobadas exitosamente al 100%.

---

## 4. Arquitectura Híbrida de Inventario y Resolución Cross-Region

Uno de los mayores desafíos arquitectónicos de la fase Gold radicó en la convivencia del procesamiento en tiempo real con el gobierno WAP:

### 4.1. Desacoplamiento de Entornos
- **Infraestructura de Streaming:** Desplegada en la región `us-east1` (Broker Apache Kafka en Compute Engine, clúster Dataproc Spark Streaming y dataset BigQuery `lumina_streaming`).
- **Data Warehouse Analítico / Sandbox:** Desplegado en multirregión `US` (`lumina_stage` y `lumina_sandbox`).

### 4.2. Restricción Regional de BigQuery
BigQuery impide transacciones directas o sentencias DML compuestas (`INSERT INTO ... SELECT ...`) entre datasets ubicados en regiones distintas (`us-east1` vs. `US`).

### 4.3. Solución Arquitectónica Híbrida Implementada
1. **Consumo de Telemetría Viva:** Los endpoints REST `/api/inventory/current` y `/api/inventory/risks` continúan consumiendo directamente las vistas deduplicadas de streaming (`stock_actual_vw` y `stock_risk_by_product_region`) en `us-east1`, garantizando frescura sub-minuto.
2. **Salvaguarda de Integridad Regional:** Ambas vistas y los endpoints aplican la restricción activa `WHERE (region IS NULL OR region != 'CYBER_TEST')`, aislando eventos de estrés inyectados durante simulaciones.
3. **Puente Orquestador WAP:** El orquestador Python (`WAPOrchestrator._write_inventory`) lee los registros limpios en `us-east1`, cruza la frontera de red hacia `US` y genera una transacción DML atómica en `lumina_sandbox.gold_inventory_current` y `gold_inventory_risks`.
4. **Auditoría y Publicación:** La auditoría `04c_wap_audit_inventory.sql` y la publicación `05_wap_publish.sql` se ejecutan localmente en `US` sin bloqueos de streaming buffer, manteniendo los 4 dominios bajo el mismo marco de gobierno corporativo.

---

## 5. Evaluación Predictiva de Demanda (Machine Learning)

El módulo predictivo tiene como propósito proyectar la demanda semanal agregada por categoría de producto para la fuente Olist (`gold_demand_olist_weekly`), compuesta por 103 semanas continuas y 74 categorías balanceadas.

### 5.1. Protocolo de Evaluación (Backtest)
- **Periodo de Prueba:** Últimas 12 semanas disponibles (`2018-06-11` a `2018-08-27`).
- **Tamaño Muestral:** Exactamente 888 observaciones de prueba (74 categorías × 12 semanas).
- **Métricas:**
  $$\text{MAE} = \frac{1}{N} \sum |y - \hat{y}|$$
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum (y - \hat{y})^2}$$
  $$\text{WAPE} = \frac{\sum |y - \hat{y}|}{\sum y} \times 100\%$$

### 5.2. Benchmark Comparativo

| Modelo | Clasificación | Observaciones | MAE | RMSE | WAPE (%) | Estado de Despliegue |
|---|---|---:|---:|---:|---:|:---:|
| **Naive Baseline ($t-1$)** | Heurístico (Persistencia) | 888 | **7.5417** | **15.9047** | **35.49%** | Referencia Óptima |
| **XGBoost Regressor** | Supervisado (Experimental) | 888 | 7.7780 | 16.7220 | 36.60% | Publicado en WAP Gold |
| **Seasonal Naive ($t-52$)** | Heurístico (Estacional Anual) | 888 | 12.7939 | 27.1788 | 60.21% | Descartado |

### 5.3. Análisis de Resultados y Hallazgos
1. **Rendimiento de XGBoost frente a Persistencia:**  
   El modelo supervisado XGBoost logró un WAPE de 36.60%, situándose muy próximo a la persistencia simple ($t-1$, 35.49%). En series de retail con categorías de baja rotación o demanda intermitente, la persistencia inmediata actúa como un estimador altamente competitivo.
2. **Falla Estructural de Seasonal Naive ($t-52$):**  
   El modelo estacional anual obtuvo un WAPE desfavorable de 60.21%. Esto se explica por la aceleración transaccional y el rápido crecimiento del marketplace de Olist entre 2017 y 2018, lo cual genera un sesgo sistemático de subestimación cuando se proyecta usando niveles de hace 52 semanas.
3. **Gobierno en WAP Gold:**  
   Las 888 predicciones y las 3 métricas oficiales de XGBoost residen en `gold_predictive_metrics` y `gold_predictive_predictions`, accesibles mediante los endpoints migrados `/api/predictive/metrics` y `/api/predictive/predictions` bajo control estricto de versión publicada (`HTTP 503` ante ausencia de versión activa).

---

## 6. Verificación, Pruebas Automatizadas y Calidad de Software

La plataforma cuenta con una suite integral de 52 pruebas automatizadas distribuidas en tres niveles:

1. **Pruebas de Aceptación del Protocolo WAP (`test_wap_acceptance.py`): 17 pruebas aprobadas.**
   - Cobertura de casos CP-01 a CP-17: publicación exitosa, concurrencia OCC, robo de lease expirado, reintentos idempotentes, detección de auditorías faltantes, fallidas o duplicadas, manifest mismatch y rollback atómico.
2. **Pruebas de API y Contratos de Datos (`test_api.py`): 13 pruebas aprobadas.**
   - Validación de los 11 endpoints analíticos en vivo contra BigQuery.
   - Respuestas HTTP 200, cardinalidades exactas (e.g. 26 inventario, 888 predicciones, 3 métricas, 3 fuentes comerciales).
   - Manejo de excepciones controladas HTTP 503 ante dominios no publicados.
3. **Pruebas de Salvaguardas, Modelado y ETL (`test_inventory_safeguards.py`, `test_stress_generators.py`, `test_uci_processing.py`, `test_ml_advanced.py`): 22 pruebas aprobadas.**
   - Exclusión de datos de estrés `CYBER_TEST`.
   - Limpieza y carga de 541,909 registros UCI sin pérdida de transacciones.
   - Generadores de carga y métricas avanzadas de machine learning.

**Total acumulado:** 52 / 52 pruebas aprobadas (100% éxito).

---

## 7. Despliegue en Producción y Operaciones en Cloud Run

La plataforma se despliega como contenedor multicapa en Google Cloud Run:
- **Servicio:** `lumina-retail`
- **Región:** `us-central1`
- **Revisión Final:** `wap-gold-final`
- **Tráfico:** 100% transferido a la revisión final auditada.
- **Seguridad:** Autenticación de infraestructura mediante Google Cloud IAM y Application Default Credentials (ADC). Ningún secreto ni credencial persistida en el repositorio.

---

## 8. Conclusiones y Trabajo Futuro

1. **Gobernanza Completa:** El protocolo WAP-02.1 demostró ser un estándar robusto para garantizar calidad sin tiempos de inactividad ni exposición de datos corruptos o intermedios en producción.
2. **Arquitectura Híbrida Validada:** La solución adoptada para el inventario en streaming preserva la reactividad en tiempo real sin romper las políticas de auditoría corporativa ni las restricciones geográficas de BigQuery.
3. **Líneas Futuras:**
   - Incorporación de características exógenas (promociones, feriados brasileños) al modelo predictivo de demanda para superar el baseline $t-1$.
   - Migración de la ingesta Kafka sobre VM hacia Google Cloud Pub/Sub completamente gestionado.
