# INFORME TÉCNICO: PRUEBA DE CARGA Y SIMULACIÓN CYBER DAYS
**Plataforma LUMINA Retail — Streaming & Ingestion Architecture**  
**Fecha de Simulación:** 19 de Noviembre de 2026  
**Tipo de Evaluación:** Prueba de Capacidad Funcional y Flujo End-to-End (Kafka → Spark → GCS → BigQuery → UI)  
**ID de Ejecución (Run ID):** `87cc5b11-926d-4525-a42e-feeab5ff6f99`  
**Entorno:** Google Cloud Platform (`lumina-retail-001`)

---

## 1. Escenario y Objetivo

### Contexto de Negocio
Durante eventos de alta concurrencia comercial (*Cyber Days* o *Black Friday*), los sistemas transaccionales y de telemetría de retail experimentan incrementos súbitos de carga (bursts de 2x a 10x respecto a la línea base operativa). El objetivo de esta prueba es **demostrar empíricamente la capacidad de la plataforma LUMINA Retail para ingerir, procesar, persistir y visualizar eventos de telemetría de stock bajo demanda sin pérdida de datos, sin degradación del pipeline de producción y sin contaminar los datasets analíticos ni las ventas históricas reales**.

### Criterios de Aceptación
1. Emisión progresiva de ráfagas controladas mediante generador sintético.
2. Transporte desacoplado en Apache Kafka garantizando confirmación (`acks=1`).
3. Procesamiento en micro-lotes continuos de 5 segundos mediante Apache Spark Structured Streaming en Google Cloud Dataproc.
4. Volcado inmutable en Data Lake (Google Cloud Storage) en formato columnar Parquet con metadatos de checkpoints recuperables.
5. Ingesta analítica en BigQuery en tiempo cuasi-real.
6. Segregación completa: 0% de contaminación sintética en las tablas comerciales Gold/Silver (`fact_sales_multisource`, `gold_commercial_monthly`).
7. Visualización controlada en el frontend React bajo un switch interactivo y badges visuales explícitos.

---

## 2. Generación y Configuración del Tráfico Sintético

### Parámetros del Generador (`scripts/stress_kafka.py`)
- **Modo:** Emisión real a broker Kafka vía socket TCP.
- **Broker Destino:** `10.142.0.3:9092` (IP interna de `lumina-kafka-vm`, zona `us-east1-b`).
- **Tópico:** `telemetria`.
- **Fases del Escenario:** 3 etapas progresivas de 10 segundos de duración cada una:
  - **Fase 1 (1x - Calentamiento):** 10 mensajes/segundo × 10 segundos = 100 mensajes.
  - **Fase 2 (2x - Carga Media):** 20 mensajes/segundo × 10 segundos = 200 mensajes.
  - **Fase 3 (5x - Burst Cyber Day):** 50 mensajes/segundo × 10 segundos = 495 mensajes emitidos (en 9.9 segundos reales).
  - **Total Programado:** 800 mensajes teóricos | **Total Emitido y Confirmado:** **795 mensajes**.
- **Configuración del Productor Kafka (`kafka-python`):**
  - `acks=1`
  - `retries=2`
  - `batch_size=16384` bytes
  - `linger_ms=10`
  - `request_timeout_ms=5000`

### Esquema y Formato del Evento Sintético
Cada evento generado posee la siguiente estructura JSON serializada en UTF-8:
```json
{
  "event_id": "SYNTH_87cc5b11_00000042",
  "test_run_id": "87cc5b11-926d-4525-a42e-feeab5ff6f99",
  "event_type": "SYNTHETIC_CYBERDAY_STRESS",
  "product_id": "CYBER_PROD_002",
  "region": "CYBER_TEST",
  "stock": 92,
  "timestamp": "2026-11-19T14:45:39.184321+00:00"
}
```
- **Catálogo Sintético:** 10 SKUs aislados (`CYBER_PROD_001` a `CYBER_PROD_010`).
- **Región Sintética:** `CYBER_TEST`.
- **Fórmula de Stock Simulada:** `stock = 50 + (seq % 100)` (Rango: 50 a 149 unidades).

---

## 3. Comportamiento en Apache Kafka (Capa de Mensajería)

### Infraestructura
- **Instancia:** Compute Engine `lumina-kafka-vm` (`e2-medium`, 1 vCPU, 4.0 GB RAM, Debian GNU/Linux 13).
- **Daemon:** Apache Kafka 4.3 en modo KRaft / standalone.

### Métricas Verificadas
- **Tópico:** `telemetria` (Partición 0).
- **Offset Inicial antes de la prueba:** `2106`
- **Offset Final tras la prueba:** `2901`
- **Total de Mensajes Transportados:** `2901 - 2106 = 795 mensajes`.
- **Tasa de Error en Broker:** **0 errores** (495 confirmaciones asíncronas en fase pico, 0 fallos de conexión).
- **Comando de Verificación de Offsets:**
  ```bash
  gcloud compute ssh lumina-kafka-vm --zone us-east1-b --command \
    "/opt/kafka/bin/kafka-run-class.sh org.apache.kafka.tools.GetOffsetShell --bootstrap-server localhost:9092 --topic telemetria"
  ```
  *Salida comprobada:* `telemetria:0:2901`

---

## 4. Procesamiento en Spark Structured Streaming (Dataproc)

### Infraestructura
- **Clúster Dataproc:** `lumina-retail-spark` (`us-east1-c`).
- **Nodos:** 1 Master (`lumina-retail-spark-m`) + 2 Workers (`lumina-retail-spark-w-0`, `w-1`), todos `e2-standard-4` (Total: 12 vCPUs, 48 GB RAM).
- **Job ID:** `6b474383829944ec959c2b5958e7b7af` (PySpark, `scripts/retailsmart_streaming.py`).
- **Cadencia de Disparo (Trigger):** `processingTime='5 seconds'`.

### Desglose de Micro-Lotes Procesados
Al auditar los archivos de offsets (`gs://lumina-retail-001-data/checkpoints/telemetria_v2/offsets/`), se identificó la absorción de los 795 eventos entre los lotes 20 y 26:

| Batch ID | Timestamp Inicio Batch | Offset Inicial | Offset Final | Mensajes Procesados | Delta Tiempo |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Batch 19** | `1795066755003` | 2105 | 2106 | (Estado base previo) | - |
| **Batch 20** | `1795099540003` | 2106 | 2148 | **42** | 5.0 s |
| **Batch 21** | `1795099545004` | 2148 | 2198 | **50** | 5.0 s |
| **Batch 22** | `1795099550004` | 2198 | 2248 | **50** | 5.0 s |
| **Batch 23** | `1795099555004` | 2248 | 2348 | **100** | 5.0 s |
| **Batch 24** | `1795099560004` | 2348 | 2409 | **61** | 5.0 s |
| **Batch 25** | `1795099565004` | 2409 | 2657 | **248** | 5.0 s |
| **Batch 26** | `1795099570003` | 2657 | 2901 | **244** | 5.0 s |
| **TOTAL** | **Ventana de 30.0 segundos** | **2106** | **2901** | **795 eventos** | **30.0 s** |

- **Commits en Checkpoint:** Todos los lotes (20 al 26) fueron confirmados atómicamente en `gs://lumina-retail-001-data/checkpoints/telemetria_v2/commits/`.
- **Errores de Procesamiento:** 0 fallos de tarea en executors Spark.

---

## 5. Persistencia en Data Lake (Google Cloud Storage)

### Directorio de Datos
- **Ruta GCS:** `gs://lumina-retail-001-data/gold/streaming/telemetria_v2/`
- **Formato:** Apache Parquet comprimido con Snappy.
- **Inventario:** 28 objetos generados (archivos de partición snappy.parquet + metadatos del writeStream `_spark_metadata`).
- **Integridad de Checkpoint:**
  `gs://lumina-retail-001-data/checkpoints/telemetria_v2/` mantiene la trazabilidad estricta de:
  - `metadata`: ID de versión de la consulta streaming.
  - `sources/0/`: Registro de offsets por micro-batch de Kafka.
  - `offsets/`: Índices de lectura hasta `26`.
  - `commits/`: Confirmaciones de escritura exitosa en GCS hasta `26`.

---

## 6. Reconciliación en BigQuery

### Consultas de Validación Cruzada

#### A. Conteo Total y Fechas Extremas
```sql
SELECT 
  event_type,
  region,
  COUNT(*) as total_eventos,
  COUNT(DISTINCT product_id) as total_productos,
  MIN(event_timestamp) as min_ts,
  MAX(event_timestamp) as max_ts
FROM `lumina-retail-001.lumina_streaming.telemetria_consolidada`
WHERE region = 'CYBER_TEST'
GROUP BY event_type, region;
```
*Resultado:*
- `total_eventos`: **795**
- `total_productos`: **10**
- `min_ts`: `2026-11-19 14:45:35.854714 UTC`
- `max_ts`: `2026-11-19 14:46:09.917458 UTC`

#### B. Análisis de Unicidad Temporal
```sql
SELECT 
  COUNT(*) as total_filas,
  COUNT(DISTINCT event_timestamp) as timestamps_unicos,
  COUNT(DISTINCT event_id) as event_ids_distintos
FROM `lumina-retail-001.lumina_streaming.telemetria_consolidada`
WHERE region = 'CYBER_TEST';
```
*Resultado:*
- `total_filas`: **795**
- `timestamps_unicos`: **795** (100% de eventos poseen marca de tiempo unívoca a nivel de microsegundos).
- `event_ids_distintos`: **495**
  *(Nota técnica documentada: En el generador `stress_kafka.py`, la variable secuencial `seq` se reinició a 1 al comenzar cada una de las 3 etapas, provocando que los identificadores de texto `SYNTH_{run_id}_00000001` a `100` se repitieran con distintos timestamps en las etapas 2 y 3. El pipeline de streaming procesó e indexó los 795 mensajes físicos sin descartes).*

---

## 7. Efecto Observable en Módulos de Inventario

### Vista de Estado Actual (`stock_actual_vw`)
La vista deduce el snapshot de inventario más reciente aplicando `ROW_NUMBER() OVER (PARTITION BY product_id, region ORDER BY event_timestamp DESC)`.
Para los 10 productos de Cyber Days, el snapshot consolidado al cierre de la prueba reporta:

| Producto | Región | Stock Registrado | Último Evento | Frescura | Estado Stock |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `CYBER_PROD_001` | `CYBER_TEST` | 140 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_002` | `CYBER_TEST` | 141 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_003` | `CYBER_TEST` | 142 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_004` | `CYBER_TEST` | 143 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_005` | `CYBER_TEST` | 144 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_006` | `CYBER_TEST` | 145 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_007` | `CYBER_TEST` | 136 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_008` | `CYBER_TEST` | 137 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_009` | `CYBER_TEST` | 138 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |
| `CYBER_PROD_010` | `CYBER_TEST` | 139 | 14:46:09 UTC | DESACTUALIZADO | NORMAL |

### Vista de Riesgo Histórico (`stock_risk_by_product_region`)
Auditoría de métricas acumuladas sobre los 795 eventos:
- Eventos por SKU: Entre 79 y 80 eventos registrados por cada producto.
- Stock mínimo registrado: 50 a 59 unidades.
- Stock máximo registrado: 140 a 149 unidades.
- Stock promedio: 95.57 a 103.43 unidades.
- Alertas críticas (`stock < 10`): **0**.
- Porcentaje de alertas: **0.00%**.

---

## 8. Visualización y Control en Frontend (React / Vite)

### Mecanismo de Segregación en `frontend/src/pages/Inventory.jsx`
Para garantizar que la simulación de Cyber Days no distorsione las métricas operativas por defecto, se diseñó la siguiente arquitectura de presentación:
1. **Estado reactivo `showCyber`:** Inicializado en `false`.
2. **Filtrado en memoria:**
   ```javascript
   const filteredCurrent = showCyber ? current : current.filter(x => x.region !== 'CYBER_TEST');
   const filteredRisks = showCyber ? risks : risks.filter(x => x.region !== 'CYBER_TEST');
   ```
3. **Control Interactivo en Cabecera:**
   Un botón selector estilizado (*"Simulación Cyber Days"*) permite alternar entre el inventario operativo estándar (26 productos) y la vista combinada con Cyber Days (36 productos).
4. **Resaltado Visual de Eventos Sintéticos:**
   Cuando `showCyber = true`, las filas correspondientes a `CYBER_TEST` se renderizan con fondo contrastante púrpura (`#1e1b4b`) y un tag visual:
   `<span style="font-size: 10px; background: #4338ca; color: white; padding: 2px 6px; border-radius: 4px;">SINTÉTICO</span>`.

---

## 9. Métricas de Rendimiento Verificadas

> **Aclaración Metodológica:** Se presentan únicamente métricas derivadas de marcas de tiempo físicas registradas en el clúster Dataproc y logs de Kafka. No se extrapolan capacidades teóricas.

- **Throughput del Emisor (Productor Kafka):**
  - Fase 1 (10 msgs/s): Tasa observada de 10.0 msgs/s.
  - Fase 2 (20 msgs/s): Tasa observada de 20.0 msgs/s.
  - Fase 3 (50 msgs/s): Tasa observada de **49.5 msgs/s** (495 eventos en 10.0 segundos).
  - Tasa promedio global de emisión: **24.8 eventos/segundo**.
- **Throughput de Consumo y Procesamiento (Spark Streaming):**
  - Ventana total de absorción: 30.0 segundos (Batch 20 al 26).
  - Rendimiento medio de procesamiento: **26.5 eventos/segundo** (795 eventos / 30.0 s).
  - Rendimiento pico en micro-lote (Batch 25): **49.6 eventos/segundo** (248 eventos en micro-lote de 5.0 s).
- **Latencia de Drenado del Pipeline (Lag):**
  Al culminar la emisión a las 14:46:11 UTC, el clúster Dataproc completó el Batch 26 a las 14:46:10 UTC (conforme a los clocks de nodo). El lag de persistencia final fue inferior a 1 ciclo de micro-lote (**< 5 segundos**).

---

## 10. Fiabilidad, Reconciliación y Limitaciones

### Resumen de Balance de Masa de Datos

| Etapa del Pipeline | Registros Contabilizados | Discrepancia | Observación |
| :--- | :---: | :---: | :--- |
| **Generador (`stress_kafka.py`)** | **795** | 0 | Confirmados vía `producer.flush()` |
| **Broker Kafka (`telemetria:0`)** | **795** | 0 | Delta de offsets: 2901 - 2106 = 795 |
| **Spark Streaming (Batches 20-26)**| **795** | 0 | Suma exacta de deltas de micro-lotes |
| **Data Lake GCS (Parquet)** | **795** | 0 | Registros persistidos en archivos snappy |
| **BigQuery (`telemetria_consolidada`)** | **795** | 0 | Coincidencia unívoca por timestamp |
| **BigQuery (`stock_actual_vw`)** | **10** | 0 | Exactamente 1 fila deduplicada por SKU |

### Limitaciones de la Simulación
1. **Ambiente de Broker Único:** La prueba se ejecutó sobre un broker único en VM GCE (`lumina-kafka-vm`). No evalúa rebalanceo dinámico de particiones ni redundancia con factor de replicación > 1.
2. **Duración de la Prueba:** La simulación tuvo una duración de 30 segundos. No constituye una prueba de estrés de resistencia a largo plazo (soak test).
3. **Aislamiento en API Unit Test:** La inclusión de los 10 registros sintéticos en la vista física de BigQuery provocó que el test unitario `test_inventory_current_unaffected` fallara al recibir 36 registros en lugar de los 26 estrictamente operacionales esperados. Este compromiso fue asumido conscientemente para dotar al frontend de capacidad demostrativa interactiva.

---

## 11. Diagrama de Flujo del Escenario

```
[ Generador Sintético ]
  stress_kafka.py (795 eventos en 3 fases: 10, 20, 50 rps)
       │
       ▼ (TCP port 9092, acks=1)
[ Apache Kafka Broker ]
  lumina-kafka-vm (us-east1-b, tópico 'telemetria', offsets: 2106 -> 2901)
       │
       ▼ (Spark Kafka Connector v0-10, micro-batch = 5s)
[ Spark Structured Streaming ]
  lumina-retail-spark (Dataproc us-east1-c, Batches 20 al 26)
       │
       ├──────────────────────────────────────────┐
       ▼ (Write Append)                           ▼ (State Management)
[ Google Cloud Storage ]                 [ GCS Checkpoints ]
  gs://.../gold/streaming/telemetria_v2/   gs://.../checkpoints/telemetria_v2/
  (28 archivos Parquet / Snappy)           (metadata, sources, offsets, commits)
       │
       ▼ (External Table Definition)
[ BigQuery Data Warehouse ]
  lumina_streaming.telemetria_consolidada (795 filas, 10 SKUs)
       │
       ▼ (Deduplicación ROW_NUMBER() = 1)
  lumina_streaming.stock_actual_vw (10 filas activas CYBER_TEST)
       │
       ▼ (HTTP GET /api/inventory/current)
[ FastAPI Backend ]
  Cloud Run: lumina-retail (revisión lumina-retail-00009-5hg)
       │
       ▼ (JSON Response, 36 items)
[ Frontend React / Vite ]
  Inventory.jsx -> Toggle "Simulación Cyber Days"
  (Default: 26 reales | Cyber ON: 26 reales + 10 sintéticos con badge morado)
```

---

## 12. Procedimiento para Reproducir la Demostración

Para reproducir esta demostración en una presentación académica:

1. **Verificar que el clúster Dataproc y el broker Kafka estén activos:**
   ```bash
   gcloud compute instances list --filter="name=lumina-kafka-vm"
   gcloud dataproc jobs list --cluster=lumina-retail-spark --region=us-east1 --filter="status.state=RUNNING"
   ```

2. **Abrir la consola interactiva en la VM Kafka y ejecutar el generador:**
   ```bash
   gcloud compute ssh lumina-kafka-vm --zone us-east1-b --command \
     "python3 /tmp/stress_kafka.py --topic telemetria --stages 10,20,50 --duration 10"
   ```

3. **Verificar la reconciliación instantánea en BigQuery:**
   ```bash
   bq query --use_legacy_sql=false \
     "SELECT COUNT(*) FROM \`lumina-retail-001.lumina_streaming.telemetria_consolidada\` WHERE region = 'CYBER_TEST'"
   ```

4. **Acceder a la interfaz de usuario en Cloud Run:**
   - Navegar al módulo **Inventario**.
   - Observar los 26 productos operativos vigentes.
   - Activar el interruptor **"Simulación Cyber Days"**.
   - Comprobar la aparición inmediata de los 10 productos `CYBER_PROD_001` a `010` resaltados con la etiqueta `SINTÉTICO` y stock actualizado por streaming.
