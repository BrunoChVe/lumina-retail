# CENTRO DE SIMULACIÓN CYBER DAYS Y CICLO DE PEDIDOS
**Plataforma LUMINA Retail — Testing Automation & Telemetry Architecture**

---

## 1. Visión General y Objetivo

El **Centro de Simulación Cyber Days** es un módulo automatizado e interactivo integrado en el dashboard de LUMINA Retail (React 19 / Vite) que permite configurar, ejecutar, monitorear en tiempo real y auditar pruebas de estrés de alta concurrencia y ciclo de pedidos e-commerce, bajo estrictos controles de aislamiento de datos y costo cero predeterminado.

---

## 2. Modalidades de Ejecución

| Característica | Modo Económico (Predeterminado) | Modo Streaming Real (Bajo Demanda) |
| :--- | :--- | :--- |
| **Infraestructura de Cómputo** | Serverless / En memoria (FastAPI) | Clúster Dataproc (12 vCPUs) + VM Kafka |
| **Costo por Hora** | **$0.00 USD** | ~$0.85 USD / hora |
| **Activación de Recursos** | Inmediata (sin arranque de VMs) | Requiere autorización explícita y arranque de GCE |
| **Flujo de Ejecución** | Hilos asíncronos en backend | Productor → Kafka → Spark → GCS → BigQuery |
| **Persistencia** | Registro unívoco en almacén de auditoría | Archivos Parquet en GCS y BigQuery Streaming |
| **Límite Seguro** | Hasta 500 pedidos por prueba | Hasta 1,000 pedidos por prueba |
| **Casos de Uso** | Pruebas funcionales del ciclo de órdenes, salvaguardas de inventario, deduplicación e idempotencia | Validación de infraestructura distribuida y pruebas de carga masiva física |

---

## 3. Simulación del Ciclo de Pedidos (Order Lifecycle)

El motor simula la secuencia causal completa del e-commerce:

```
[ Cliente / Carrito ]
         │
         ▼
  1. order_created ─────────────► [ Registro del intento de compra ]
         │
         ▼
  2. order_item_created ────────► [ Desglose de SKU, cantidad y precio ]
         │
         ▼
   ¿Stock suficiente?
   ├── SÍ ──► 3. inventory_decrement ──► [ Deducción estricta de existencias ]
   │                 │
   │                 ▼
   │          ¿Stock <= 20? ──► (Opcional) 4. inventory_low [ Alerta preventiva ]
   │                 │
   │                 ▼
   │          5. order_completed ──────► [ Orden aprobada con total en PEN ]
   │
   └── NO ──► 6. order_rejected ───────► [ Rechazo por Out of Stock (Stock no negativo) ]
```

### Reglas de Negocio Implementadas
1. **Identificadores Unívocos:** Cada orden genera un `order_id` (ej. `ORD_CYBER_{run_id[:8]}_{seq}`) y cada evento un `event_id` (ej. `EVT_{run_id[:8]}_{event_seq}`) único e irrepetible.
2. **Prevención de Stock Negativo:** El inventario se valida antes de procesar el pedido. Si `requested_qty > current_stock`, se emite `order_rejected` y el inventario permanece inalterado.
3. **Control de Idempotencia y Deduplicación:** Si un pedido ya procesado reintenta ejecutarse, el motor detecta la duplicidad por `order_id`, emite un evento `duplicate_order_neutralized` con acción `IDEMPOTENT_IGNORE` y **no descuenta stock adicional**.
4. **Catálogo Aislado:** Opera sobre productos sintéticos `CYBER_SKU_001` a `CYBER_SKU_010`, impidiendo cualquier colisión con los productos reales de Olist, TheLook o UCI.
5. **Etiquetado Transaccional:** Todos los registros incorporan `synthetic_flag = true` y no tocan las tablas Gold operativas.

---

## 4. Endpoints de la API FastAPI

| Método | Endpoint | Descripción | Control de Seguridad |
| :---: | :--- | :--- | :--- |
| `GET` | `/api/simulation/modalities` | Consulta modalidades disponibles, límites y costos | Público |
| `GET` | `/api/simulation/infrastructure_status` | Verifica estado de VM Kafka y Dataproc en GCP | Solo lectura de estado |
| `POST` | `/api/simulation/validate_config` | Valida límites de pedidos, productos y autorización | Validación sin efectos secundarios |
| `POST` | `/api/simulation/run` | Inicia una simulación en segundo plano | **Control de Concurrencia:** Solo 1 simulación activa |
| `GET` | `/api/simulation/status/{run_id}` | Progreso en tiempo real, KPIs y estado del stock | Polling ligero |
| `GET` | `/api/simulation/events/{run_id}` | Log de eventos cronológico con filtro por tipo | Paginación (límite máx. 500) |
| `GET` | `/api/simulation/history` | Historial de todas las pruebas ejecutadas | Preserva ejecuciones históricas |
| `POST` | `/api/simulation/cancel/{run_id}` | Cancela de forma segura una prueba en curso | Parada controlada de hilos |

---

## 5. Panel de Control en Frontend (React)

El módulo se encuentra disponible en la barra lateral bajo **Centro de Simulación**:
1. **Pestaña 1 — Configuración y Ejecución:**
   - Selector visual de modalidad (Económico vs. Streaming Real).
   - Selector de escenario (`ORDER_CYCLE`, `BURST_TRAFFIC`, `INVENTORY_DEPLETION`, `IDEMPOTENCY_STRESS`).
   - Sliders de pedidos (10 a 300), productos sintéticos (2 a 10) y stock inicial.
   - Banner de advertencia de costos para Streaming Real con checkbox de autorización obligatoria.
   - Botón de acción con feedback de progreso.
2. **Pestaña 2 — Monitoreo en Vivo:**
   - Barra de progreso porcentual dinámica con polling automático (1.2s).
   - 6 Tarjetas de KPIs en vivo: Pedidos Totales, Aprobados, Rechazados, Eventos, Throughput y Duración.
   - Gráfico de barras de distribución de eventos por tipo.
   - Tabla en vivo de estado de existencias por SKU (`Stock Inicial`, `Stock Remanente`, `Ventas`, `Rechazos`).
   - Log cronológico de eventos con selector de filtro por tipo de evento.
3. **Pestaña 3 — Historial y Auditoría:**
   - Tabla histórica inmutable de pruebas.
   - Preserva la ejecución histórica de referencia: `87cc5b11-926d-4525-a42e-feeab5ff6f99` (795 eventos procesados en Dataproc Spark y BigQuery).
   - Botón para reabrir y auditar cualquier ejecución pasada.

---

## 6. Pruebas Automatizadas

La suite `backend/tests/test_simulation_engine.py` valida rigurosamente:
- Validación de configuración y rechazo de límites inseguros.
- Bloqueo de Streaming Real si no se provee `authorized = True`.
- Ejecución completa del ciclo de pedidos en modo económico.
- Deduplicación e idempotencia con neutralización de pedidos repetidos.
- Prevención matemática de stock negativo en todos los SKUs.
- Cancelación segura de simulaciones.
- Preservación de la ejecución histórica de 795 eventos.

*Resultado:* **75/75 pruebas del backend aprobadas al 100%**.
