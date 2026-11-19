# RetailSmart

**Plataforma de analítica comercial y logística multisource**

RetailSmart integra fuentes de comercio electrónico para analizar ventas, productos, categorías y desempeño logístico mediante procesamiento batch, streaming y visualización.

## 1. Arquitectura

| Componente | Tecnología |
|---|---|
| Frontend | React, Vite, Recharts |
| Backend | Python, FastAPI |
| Data Lake | Google Cloud Storage |
| Data Warehouse | BigQuery |
| Procesamiento | Apache Spark, Dataproc |
| Mensajería | Apache Kafka |
| Machine Learning | XGBoost, Scikit-learn |
| Despliegue | Google Cloud Run |

## 2. Fuentes de datos

- **Olist:** comercio electrónico brasileño. Moneda BRL (Moneda documentada).
- **TheLook:** comercio electrónico internacional. Moneda USD (Moneda confirmada para el proyecto).
- **UCI Online Retail:** transacciones comerciales del Reino Unido y Europa. Moneda GBP (Moneda documentada).

Los indicadores monetarios se mantienen rigurosamente separados por fuente (BRL, USD y GBP). La columna `currency_code` identifica la moneda en las tablas y vistas, pero no impide matemáticamente las sumas accidentales entre divisas distintas si una consulta las omite; por tanto, los reportes, dashboards y endpoints analíticos deben agrupar o filtrar obligatoriamente por moneda. Los módulos comerciales y logísticos utilizan poblaciones y criterios diferentes según la disponibilidad de origen (UCI no dispone de métricas de tránsito o entrega logística).

## 3. Procesamiento batch

El procesamiento implementado para Olist sigue una arquitectura Medallion:

- **Bronze:** datos de origen.
- **Silver:** limpieza y transformación.
- **Gold:** resultados analíticos.

Scripts principales:

- `lumina_retail_pipeline.py`: procesamiento hacia Silver.
- `lumina_retail_gold.py`: generación de resultados Gold.
- `retailsmart_enrich_regions.py`: enriquecimiento por macroregiones brasileñas.

TheLook se utiliza como fuente adicional multisource; no se atribuye automáticamente el mismo pipeline batch.

## 4. Streaming y recuperación ante fallos

### Arquitectura y flujo de telemetría
El pipeline de eventos de stock en tiempo real opera según el siguiente desacoplamiento:

`Kafka (Broker VM) → Spark Structured Streaming (Dataproc) → Google Cloud Storage (Parquet) → BigQuery (External Tables / Views)`

### Configuración real del entorno
- **Broker Kafka:** Instancia Compute Engine `lumina-kafka-vm` (`10.142.0.3:9092`, zona `us-east1-b`, tipo `e2-medium`). Despliegue mono-broker sobre Linux.
- **Tópico:** `telemetria` (partición única, retención por defecto).
- **Esquema del evento:** JSON conteniendo `event_id`, `product_id`, `region`, `stock`, `event_type` y `timestamp`.
- **Motor de procesamiento:** Clúster Dataproc `lumina-retail-spark` (`us-east1-c`, 1 máster + 2 workers `e2-standard-4`).
- **Script principal:** `scripts/retailsmart_streaming.py`, ejecutando Spark Structured Streaming con micro-batches cada 5 segundos (`trigger(processingTime="5 seconds")`), `startingOffsets="latest"` y `failOnDataLoss="false"`.
- **Persistencia en Data Lake:** Volcado en formato Parquet en `gs://lumina-retail-001-data/gold/streaming/telemetria_v2/`.
- **Checkpoints de recuperación:** Almacenamiento persistente de offsets y commits en `gs://lumina-retail-001-data/checkpoints/telemetria_v2/`.
- **Capa analítica en BigQuery:** Tabla externa `lumina_streaming.telemetria_events_v2_audit` sobre GCS, consolidada en la vista `telemetria_consolidada` y deduplicada por producto-región en `stock_actual_vw`.

### Evidencia de la prueba de recuperación controlada

| Métrica / Indicador | Resultado Comprobado | Estado |
|---|---:|:---:|
| Registros auditados | 304 | Verificado |
| Eventos únicos procesados | 304 | Verificado |
| Duplicados detectados | 0 | Verificado |
| Evento inyectado durante interrupción | 1 | Recuperado |

La prueba se ejecutó interrumpiendo el flujo activo, emitiendo telemetría de prueba en Kafka y ejecutando `scripts/retailsmart_streaming_test.py` con `trigger(availableNow=True)` apuntando al mismo directorio de checkpoints en GCS. Spark leyó los offsets no confirmados, procesó los mensajes acumulados y confirmó los commits sin duplicar ningún evento previo.

### Procedimiento paso a paso para recuperación operativa
Ante una caída imprevista del job de streaming o de la infraestructura:

1. **Garantía contra ejecución concurrente (Crítico):**
   Verificar que **no exista ningún otro job activo** utilizando el mismo directorio de checkpoints en GCS. Ejecutar dos jobs concurrentes sobre el mismo `checkpointLocation` corrompe los metadatos de offsets y commits.
   ```bash
   gcloud dataproc jobs list --region=us-east1 --filter="status.state=RUNNING" --project=lumina-retail-001
   ```
   Si existe un job colgado o en fallo, cancelarlo explícitamente antes de continuar:
   ```bash
   gcloud dataproc jobs kill <JOB_ID> --region=us-east1 --project=lumina-retail-001
   ```

2. **Diagnóstico de estado y lag:**
   Ejecutar `python scripts/monitor_retailsmart.py` para comparar el último offset registrado en Kafka frente al último offset confirmado en los checkpoints de Spark (`lag = kafka_offset - spark_offset`).

3. **Inspección de checkpoints en GCS:**
   Verificar la existencia de los metadatos de progreso en Cloud Storage:
   ```bash
   gcloud storage ls gs://lumina-retail-001-data/checkpoints/telemetria_v2/commits/ --project=lumina-retail-001
   ```

4. **Reinicio del job con preservación de estado:**
   Relanzar el job en Dataproc reutilizando exactamente la misma ruta `CHECKPOINT_PATH`.
   - **Comportamiento de `startingOffsets=latest`:** En un arranque inicial (sin checkpoint previo), `latest` descarta los mensajes acumulados en Kafka previos al inicio del job. No obstante, al reutilizar un checkpoint existente, Spark **ignora** la directiva `latest` y reanuda estrictamente desde el siguiente offset confirmado en los metadatos.
   ```bash
   gcloud dataproc jobs submit pyspark scripts/retailsmart_streaming.py \
     --cluster=lumina-retail-spark \
     --region=us-east1 \
     --jars=scripts/spark-kafka/spark-sql-kafka-0-10_2.12-3.5.3.jar,scripts/spark-kafka/kafka-clients-3.4.1.jar,scripts/spark-kafka/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,scripts/spark-kafka/commons-pool2-2.11.1.jar \
     --project=lumina-retail-001
   ```

5. **Validación de vaciado de cola (opcional):**
   Si se requiere procesar de golpe todos los datos acumulados sin dejar un job en ejecución continua, utilizar `scripts/retailsmart_streaming_test.py` (`availableNow=True`).

### Distinción de garantías reales y comportamiento ante fallos

| Componente | Garantía Real / Clasificación | Comportamiento ante Fallo |
|---|---|---|
| **Apache Kafka** | Semántica sujeta a configuración | La persistencia depende del periodo de retención del log. No se debe asumir *at-least-once* como garantía comprobada sin verificar formalmente los parámetros del productor (`acks`, `retries`) y del broker. No previene duplicados en publicación. |
| **Spark Structured Streaming** | Procesamiento *at-least-once* (en sink de archivos) | Si Spark procesa un micro-lote y escribe los archivos Parquet en GCS pero falla antes de escribir el archivo de commit en el checkpoint, al reiniciar **reprocesará el micro-lote completo**, escribiendo nuevos archivos Parquet y dejando archivos huérfanos del intento fallido en GCS. |
| **GCS Parquet Sink** | Almacenamiento *at-least-once* | No implementa transaccionalidad ACID atómica nativa; puede contener archivos huérfanos o duplicados resultantes de micro-lotes reintentados tras caídas no limpias. |
| **BigQuery (`stock_actual_vw`)** | Deduplicación lógica del estado actual por producto y región | Aplica ventana analítica (`ROW_NUMBER() OVER (PARTITION BY product_id, region ORDER BY event_timestamp DESC, ingested_at DESC)`). Reconstruye el último estado de stock, pero no constituye exactamente-una-vez de extremo a extremo. |

### Alcance de la deduplicación analítica
- **Protección de estado actual:** La vista `stock_actual_vw` aísla y deduplica con éxito el último nivel de stock por producto y región, garantizando que el dashboard no presente duplicados de inventario vivo.
- **Limitación en histórico de eventos:** La vista `telemetria_consolidada` realiza un `UNION ALL` directo de las tablas externas. Si existen archivos Parquet duplicados en GCS producto de reintentos, las consultas sobre el histórico de eventos los contabilizarán repetidos salvo que se aplique una deduplicación explícita por `event_id`.

### Limitaciones actuales y riesgos técnicos
- **Punto único de fallo (SPOF):** La ingesta reside en una única máquina virtual (`lumina-kafka-vm`). Si la VM se detiene, la memoria se agota o el disco se satura, toda la ingesta se paraliza. **No existe alta disponibilidad activa-activa ni failover automático**.
- **Riesgo de expiración en cola:** Si el tiempo de recuperación supera la política de retención de Kafka (`log.retention.hours`), los eventos no leídos se perderán irremediablemente.
- **Riesgo de micro-archivos:** La frecuencia de micro-batches a 5 segundos genera cientos de archivos Parquet pequeños por hora en GCS, degradando progresivamente el tiempo de consulta de las tablas externas en BigQuery.

### Mejoras recomendadas para producción
1. **Migración a Google Cloud Pub/Sub:** Sustituir la VM de Kafka por Pub/Sub gestionado para eliminar el SPOF, habilitar escalabilidad elástica sin gestión de servidores y asegurar retención redundante multi-zona.
2. **Compactación de micro-archivos Parquet:** Programar un job periódico en Dataproc Serverless que fusione los micro-parquets generados cada 5 segundos en archivos grandes optimizados para BigQuery, mitigando el *small-file problem*.
3. **Alertas automáticas en Cloud Monitoring:** Configurar métricas de alerta basadas en el log lag de Kafka y en el estado de frescura de la telemetría.

## 5. Modelado predictivo de demanda (Machine Learning)

Se evaluó la predicción de demanda semanal agregada (líneas de artículo) por categoría de producto para la fuente Olist (`gold_demand_olist_weekly`).

### Conjunto de datos y partición temporal
- **Histórico analizado:** 103 fechas semanales consecutivas entre el `2016-09-12` y el `2018-08-27` para 74 categorías de productos, estructuradas en un panel continuo balanceado con imputación de ceros en semanas sin ventas.
- **Ventana de entrenamiento:** Semanas anteriores al `2018-06-11`.
- **Ventana de prueba (Backtest):** Últimas 12 semanas disponibles (`2018-06-11` a `2018-08-27`), totalizando exactamente **888 observaciones** (74 categorías × 12 semanas).

### Modelos evaluados
1. **XGBoost (Modelo experimental):** Regresor supervisado (`XGBRegressor`) con 11 variables de retardo (`lag_1`, `lag_2`, `lag_4`, `lag_8`, `lag_13`, `lag_26`), medias móviles (`rolling_mean_4`, `rolling_mean_8`, `rolling_mean_13`) y componentes de calendario (`month`, `week_of_year`). Se conserva como modelo experimental base del proyecto.
2. **Naive Baseline ($t-1$):** Pronóstico de persistencia simple basado en el valor real observado en la semana inmediatamente anterior para la misma categoría ($\hat{y}_{c,t} = y_{c,t-1}$).
3. **Seasonal Naive Baseline ($t-52$):** Pronóstico basado en el valor real observado en la misma semana del año anterior ($\hat{y}_{c,t} = y_{c,t-52}$).

### Resultados comparativos (888 observaciones evaluadas)

| Modelo | Tipo | Observaciones | MAE | RMSE | WAPE |
|---|---|---:|---:|---:|---:|
| **Naive Baseline ($t-1$)** | Heurístico (Persistencia) | 888 | **7.5417** | **15.9047** | **35.49%** |
| **XGBoost** | Supervisado (Experimental) | 888 | 7.7780 | 16.7220 | 36.60% |
| **Seasonal Naive ($t-52$)** | Heurístico (Estacional anual) | 888 | 12.7939 | 27.1788 | 60.21% |

### Hallazgos técnicos
- **Mejor modelo del backtest:** El modelo **Naive ($t-1$)** obtuvo el mejor rendimiento en las tres métricas evaluadas, registrando un WAPE de 35.49% frente al 36.60% de XGBoost.
- **Comportamiento de XGBoost:** El modelo no supera a la persistencia simple en este corte temporal. Se mantiene como hipótesis pendiente de validación si esto responde a un sobreajuste en los hiperparámetros, a la sensibilidad de la función de pérdida cuadrática ante categorías de bajo volumen, o a la necesidad de incorporar covariables exógenas (promociones, feriados locales). XGBoost se conserva íntegramente como modelo experimental en el repositorio.
- **Rendimiento de Seasonal Naive:** Presenta un error sustancialmente mayor (WAPE de 60.21%). Como hipótesis explicativa, el fuerte crecimiento interanual del volumen transaccional de Olist entre 2017 y 2018 provoca que las referencias de hace 52 semanas subestimen de forma sistemática la escala de demanda del periodo evaluado.

## 6. Dashboard

- **Overview:** indicadores generales.
- **Commercial:** ventas, evolución mensual, categorías y productos.
- **Logistics:** envíos, entregas y cobertura.
- **Sources:** información de las fuentes.
- **Inventory:** monitoreo de stock en tiempo real, frescura de telemetría y focos de riesgo.
- **Predictive:** evaluación de desempeño del modelo de demanda, métricas MAE/RMSE/WAPE y errores por categoría.

Los valores no disponibles se representan como nulos, no como cero. La tasa de entregas tardías de TheLook no está disponible.

## 7. API REST

| Endpoint | Función |
|---|---|
| `/api/health` | Estado del servicio |
| `/api/commercial/summary` | Resumen comercial |
| `/api/commercial/monthly` | Evolución mensual |
| `/api/commercial/categories` | Categorías |
| `/api/commercial/products` | Productos |
| `/api/logistics/summary` | Resumen logístico |
| `/api/logistics/monthly` | Evolución logística |
| `/api/inventory/current` | Stock actual y frescura de telemetría |
| `/api/inventory/risks` | Análisis histórico de riesgo de stock |
| `/api/predictive/metrics` | Métricas del modelo de demanda |
| `/api/predictive/predictions` | Predicciones semanales por categoría |

## 8. Ejecución local

Requisitos: Python 3.12, Node.js, npm y credenciales autorizadas de Google Cloud.

**Backend:**

1. Acceder a `backend/`.
2. Crear y activar un entorno virtual.
3. Instalar dependencias con `pip install -r requirements.txt`.
4. Ejecutar `gcloud auth application-default login`.
5. Iniciar con `uvicorn app.main:app --reload --port 8080`.

**Frontend:**

1. Abrir otra terminal y acceder a `frontend/`.
2. Instalar dependencias con `npm ci`.
3. Iniciar con `npm run dev`.

Vite utiliza el proxy `/api` para comunicarse con el backend local en el puerto 8080.

## 9. Docker

El Dockerfile raíz utiliza construcción multietapa: Node.js compila el frontend y Python ejecuta FastAPI.

La imagen se construye con:

`docker build -t retailsmart:latest .`

## 10. Despliegue y seguridad

La aplicación se despliega en Google Cloud Run con acceso protegido mediante Identity-Aware Proxy (IAP). La API utiliza una cuenta de servicio con permisos para consultar BigQuery.

Buenas prácticas:
- No almacenar credenciales ni claves privadas en el repositorio.
- Utilizar credenciales autorizadas para acceder a Google Cloud.
- Aplicar permisos mínimos necesarios.
- Excluir archivos de entorno, datos locales y respaldos del control de versiones.

## 11. Validación técnica

Durante la evaluación se verificaron:

- Estado y sincronización de Git.
- Búsqueda básica de archivos sensibles y patrones de secretos.
- Lint y compilación del frontend con Vite (`dist/` generado exitosamente en `< 800 ms`).
- Sintaxis y dependencias del backend.
- Pruebas automatizadas locales: **19/19 pruebas reportadas aprobadas** (11 en `backend/tests/test_api.py` y 8 en `backend/tests/test_uci_processing.py`).

### Distinción entre entorno local y producción (Cloud Run)
- **Capacidades operativas locales y Gold WAP:**
  - Backend FastAPI con 11 endpoints activos gobernados y conectados a BigQuery (`lumina_sandbox` y `lumina_streaming`).
  - Implementación del protocolo **Write-Audit-Publish (WAP-02.1)** con control de concurrencia optimista (OCC), *fencing tokens* monotónicos, *leasing* y 15 scripts SQL.
  - **4/4 Dominios publicados en Gold:** Commercial, Logistics, Inventory y Predictive con 16/16 auditorías superadas al 100%.
  - Frontend React 19 compilado con 6 módulos: Overview, Commercial, Logistics, Sources (Olist, TheLook y UCI), Inventory (tiempo real + telemetría) y Predictive (WAP Gold + Benchmarks).
  - Integración analítica completa de UCI Online Retail (541,909 registros en `stg_uci_online_retail`, `vw_uci_commercial_monthly` y `vw_sales_multisource_with_uci`).
  - Suite de pruebas automatizadas: **52/52 pruebas aprobadas** (17 de aceptación WAP, 13 de API y contratos, y 22 de salvaguardas, ETL y machine learning).
- **Capacidades desplegadas en Cloud Run:**
  - Servicio `lumina-retail` en `us-central1`.
  - Revisión `wap-gold-final` con soporte para los 11 endpoints, interfaz de usuario completa y gobernanza WAP activa con 100% del tráfico asignado.

Estas comprobaciones no equivalen a una auditoría integral de seguridad ni a una medición exhaustiva de cobertura de líneas mediante herramientas de cobertura de código.

## 12. Gobernanza WAP y Control de Versiones

El acceso a los datos analíticos Gold está condicionado a la existencia de una versión activa en `lumina_sandbox.gold_release_control`:
- Si un dominio no ha sido publicado o se encuentra en estado `EMPTY`, la API devuelve un código de error controlado `HTTP 503 Service Unavailable`.
- En caso de anomalías en producción, el script `scripts/wap/06_wap_rollback.sql` permite restituir la versión anterior de forma inmediata e idempotente.

## 13. Limitaciones y mejoras futuras

- Incorporar pruebas automatizadas.
- Parametrizar la configuración del backend.
- Fortalecer el manejo de errores.
- Implementar monitoreo y alertas automáticas.
- Mejorar la trazabilidad entre código, imágenes y despliegues.
- Ampliar las pruebas de recuperación.
- Documentar la reconciliación de indicadores comerciales y logísticos.

---

**RetailSmart** — Proyecto de ingeniería de datos y analítica multisource.
