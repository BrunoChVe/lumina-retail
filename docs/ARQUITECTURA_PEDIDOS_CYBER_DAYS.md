# ARQUITECTURA DE FLUJO DE TELEMETRÍA Y CICLO DE PEDIDOS (CYBER DAYS)

Este documento detalla la arquitectura implementada para la ingesta de telemetría de alto volumen (Cyber Days) y describe la propuesta evolutiva para la integración del ciclo completo de pedidos transaccionales.

---

## 1. Nivel 1 — Arquitectura de Telemetría Streaming (Implementada y Validada)

### 1.1. Objetivo
Ingerir, procesar, persistir y visualizar actualizaciones de inventario en tiempo cuasi-real durante picos masivos de demanda, sin impactar ni saturar el backend transaccional OLTP de LUMINA Retail.

### 1.2. Componentes de la Arquitectura
- **Productor / Inyector (`scripts/stress_kafka.py`):** Generador de carga programable que simula ráfagas (*bursts*) asíncronas de actualizaciones de stock. Permite configurar eventos, tópicos y ratios de TPS (Transaction Per Second).
- **Apache Kafka (`lumina-kafka-vm`, Zona `us-east1-b`):** Message Broker en configuración mono-nodo (KRaft). Garantiza durabilidad transitoria y encolamiento (`acks=1`) del tópico `telemetria`.
- **Dataproc Spark Structured Streaming (`lumina-retail-spark`):** Motor de micro-lotes configurado con *triggers* cada 5 segundos. Actúa como consumidor del tópico, aplicando transformaciones ligeras en PySpark y deduplicación a nivel partición.
- **Google Cloud Storage (Data Lake):** Persistencia inmutable del flujo bajo el formato analítico `.parquet` y almacenamiento de Checkpoints (Write-Ahead Logs, offsets de Kafka y commits) para garantía de recuperación ante fallos.
- **BigQuery (`lumina_streaming`):** Consultas federadas (Tablas Externas) directamente sobre el Data Lake. Las vistas lógicas `telemetria_consolidada` y `stock_actual_vw` efectúan la deduplicación analítica final.
- **FastAPI / React:** Consulta en vivo desde el frontend. Dispone de un mecanismo de segregación (`include_synthetic`) para visualizar independientemente los inventarios operativos y los generados en el estrés sintético.

---

## 2. Nivel 2 — Propuesta de Evolución: Ciclo Completo de Pedidos

Actualmente la plataforma monitoriza "estados de stock absolutos" inyectados pasivamente. La siguiente evolución arquitectónica propone integrar el **flujo causal** de los pedidos (Order Lifecycle), en el que el stock es consecuencia de operaciones orquestadas.

### 2.1. Secuencia de Eventos del Ciclo de Pedido
El bus de Kafka expandirá sus tópicos para albergar la semántica de la máquina de estados de órdenes:
1. `order_created`: Intención de compra emitida por el carrito del eCommerce.
2. `order_item_created`: Desglose del ticket.
3. `inventory_decrement`: Sub-evento de reserva de stock.
4. `inventory_low`: Evento crítico si el `inventory_decrement` deja el stock por debajo del umbral de seguridad.
5. `order_rejected`: Si la reserva falla por desabastecimiento.
6. `order_completed`: Pago confirmado, el stock reservado se descuenta definitivamente.

### 2.2. Reglas de Negocio a Implementar
- **Protección de Reservas:** El stock disponible se formula como `Stock Físico - Reservas Pendientes`. Un `order_created` reduce el disponible inmediatamente, previniendo sobreventa.
- **Idempotencia Transaccional:** Cada evento dispondrá de un `event_id` único inyectado en un *Key-Value Store* intermedio (ej. Redis o Memorystore) para evitar el re-procesamiento de retrys del productor Kafka.
- **Aislamiento de la Demanda Histórica:** Las fuentes planas históricas (como **UCI Online Retail**) actuarán exclusivamente como tensores para predicción de demanda teórica. Cuando el sistema evalúe un "pedido", el descuento de inventario jamás aplicará sobre métricas de UCI, pues la fuente carece de bodegas y reposición física.

### 2.3. Arquitectura Técnica Propuesta (End-to-End)
```
[ Frontend eCommerce ] ──(REST POST)──► [ FastAPI Order Service ]
                                                 │
                                                 ▼ (Kafka Producer)
                                         [ Kafka: orders_topic ]
                                                 │
                                                 ▼
             [ Flink / Spark Streaming (Order & Inventory Orchestrator) ]
                │                                │
                ▼ (Redis / Memorystore)          ▼ (Kafka: inventory_topic)
      [ Idempotency Cache ]            [ Actualización de Bodega ]
```
1. **Orquestación en Stream:** Un Job de Spark leerá de `orders_topic` y cruzará contra el estado de inventario para decidir si emite `order_rejected` o `order_completed`.
2. **Persistencia Híbrida:** Las órdenes completadas se guardarán en BigLake (BigQuery + Iceberg) habilitando transaccionalidad ACID directa en Data Warehouse.

*(Esta segunda fase se presenta como diseño de referencia (Blueprint) y no se encuentra actualmente desplegada en el entorno de producción)*.