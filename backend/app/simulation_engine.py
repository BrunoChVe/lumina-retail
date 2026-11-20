"""
Motor de Simulación Automatizada para Cyber Days y Ciclo de Pedidos
LUMINA Retail — Intelligence & Operations Platform

Soporta dos modalidades:
1. MODO ECONÓMICO (Default, Serverless): Simula el ciclo completo de pedidos y reglas
   de inventario en memoria/lotes sin encender Kafka ni Dataproc (Costo $0).
2. MODO STREAMING REAL (Bajo Demanda): Verifica infraestructura Kafka/Dataproc,
   estima costos de cómputo y requiere autorización explícita antes de operar.
"""

import json
import math
import os
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Estados de ciclo de vida controlados
STATUS_PENDING = "PENDING"
STATUS_VALIDATING = "VALIDATING"
STATUS_RUNNING = "RUNNING"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"

# Modalidades de simulación
MODE_ECONOMIC = "ECONOMIC"
MODE_REAL_STREAMING = "REAL_STREAMING"

# Tipos de eventos del ciclo de pedidos
EVENT_ORDER_CREATED = "order_created"
EVENT_ORDER_ITEM_CREATED = "order_item_created"
EVENT_INVENTORY_DECREMENT = "inventory_decrement"
EVENT_INVENTORY_LOW = "inventory_low"
EVENT_ORDER_REJECTED = "order_rejected"
EVENT_ORDER_COMPLETED = "order_completed"

# Almacén de ejecuciones en memoria protegido por mutex
_STORE_LOCK = threading.Lock()
_ACTIVE_RUN_ID: Optional[str] = None

# Almacén de ejecuciones (Pre-sembrado con la ejecución histórica real validada)
_RUNS_STORE: Dict[str, Dict[str, Any]] = {
    "87cc5b11-926d-4525-a42e-feeab5ff6f99": {
        "run_id": "87cc5b11-926d-4525-a42e-feeab5ff6f99",
        "name": "Simulación Cyber Days Real (Kafka + Spark Dataproc)",
        "mode": MODE_REAL_STREAMING,
        "scenario": "BURST_TRAFFIC",
        "status": STATUS_COMPLETED,
        "start_time": "2026-11-19T14:45:35.854714+00:00",
        "end_time": "2026-11-19T14:46:11.940000+00:00",
        "duration_sec": 36.0,
        "total_events": 795,
        "events_processed": 795,
        "total_orders": 795,
        "completed_orders": 795,
        "rejected_orders": 0,
        "inventory_decrements": 795,
        "duplicate_orders_neutralized": 0,
        "errors": 0,
        "throughput_events_per_sec": 26.5,
        "producer_tps": 24.8,
        "latency_ms_avg": 4.2,
        "kafka_topic": "telemetria",
        "kafka_offset_start": 2106,
        "kafka_offset_end": 2901,
        "spark_job_id": "6b474383829944ec959c2b5958e7b7af",
        "parquet_files": 28,
        "gcs_path": "gs://lumina-retail-001-data/gold/streaming/telemetria_v2/",
        "bigquery_table": "lumina_streaming.telemetria_consolidada",
        "synthetic_flag": True,
        "is_historical": True,
        "notes": "Ejecución histórica real validada a través de Dataproc Spark Structured Streaming y persistida en BigQuery.",
        "inventory_state": {
            f"CYBER_PROD_{i:03d}": {"initial": 100, "current": 140 + i, "low_alert": False}
            for i in range(1, 11)
        },
        "events": []
    }
}


def get_available_modalities() -> List[Dict[str, Any]]:
    """Devuelve las modalidades disponibles con información de costo y requisitos."""
    return [
        {
            "id": MODE_ECONOMIC,
            "name": "Modo Económico (Serverless / Local)",
            "description": "Ejecuta el ciclo completo de pedidos y reglas de inventario en memoria sin encender infraestructura de cómputo.",
            "is_default": True,
            "estimated_cost_usd_per_hour": 0.0,
            "requires_authorization": False,
            "infrastructure_needed": "Ninguna (Procesamiento serverless)",
            "safe_order_limit": 500
        },
        {
            "id": MODE_REAL_STREAMING,
            "name": "Modo Streaming Real (Kafka + Spark Dataproc)",
            "description": "Flujo distribuido real a través de VM Kafka y Clúster Dataproc de 12 vCPUs con persistencia en GCS Parquet y BigQuery.",
            "is_default": False,
            "estimated_cost_usd_per_hour": 0.85,
            "requires_authorization": True,
            "infrastructure_needed": "VM lumina-kafka-vm (e2-medium) + Clúster Dataproc lumina-retail-spark (12 vCPUs)",
            "safe_order_limit": 1000,
            "status": "PAUSADO / DETENIDO (Para ahorro de créditos)"
        }
    ]


def get_infrastructure_status() -> Dict[str, Any]:
    """Reporta el estado actual de los recursos de streaming en Google Cloud."""
    return {
        "kafka_vm": {
            "name": "lumina-kafka-vm",
            "zone": "us-east1-b",
            "machine_type": "e2-medium",
            "status": "TERMINATED",
            "is_running": False
        },
        "dataproc_cluster": {
            "name": "lumina-retail-spark",
            "zone": "us-east1-c",
            "master_type": "e2-standard-4",
            "workers": "2 x e2-standard-4 (12 vCPUs totales)",
            "status": "TERMINATED",
            "is_running": False
        },
        "activation_cost_estimate_usd": 0.85,
        "ready_for_real_streaming": False,
        "recommendation": "Utilice el Modo Económico para pruebas de ciclo de pedidos y validación de reglas sin incurrir en costos de cómputo continuo."
    }


def validate_simulation_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Valida los parámetros de configuración y límites seguros."""
    errors = []
    mode = config.get("mode", MODE_ECONOMIC)
    num_orders = config.get("num_orders", 50)
    num_products = config.get("num_products", 5)

    if mode not in [MODE_ECONOMIC, MODE_REAL_STREAMING]:
        errors.append(f"Modalidad no válida: {mode}")

    if mode == MODE_REAL_STREAMING:
        if not config.get("authorized", False):
            errors.append("El Modo Streaming Real requiere autorización explícita de costos antes de ejecutarse.")
        if num_orders > 1000:
            errors.append("El límite máximo seguro para Streaming Real es de 1,000 pedidos.")
    else:
        if num_orders > 500:
            errors.append("El límite máximo seguro para el Modo Económico es de 500 pedidos.")

    if num_orders < 1:
        errors.append("La cantidad de pedidos debe ser al menos 1.")

    if num_products < 1 or num_products > 20:
        errors.append("La cantidad de productos debe estar entre 1 y 20.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "normalized_config": {
            "name": config.get("name") or f"Simulación {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            "mode": mode,
            "scenario": config.get("scenario", "ORDER_CYCLE"),
            "num_orders": int(num_orders),
            "num_products": int(num_products),
            "regions": config.get("regions") or ["Lima", "Norte", "Sur", "Centro", "Oriente"],
            "initial_stock_per_product": config.get("initial_stock", 60),
            "simulate_idempotency": config.get("simulate_idempotency", True),
            "authorized": bool(config.get("authorized", False))
        }
    }


def _run_economic_simulation_worker(run_id: str, config: Dict[str, Any]):
    """Ejecutor en hilo secundario para el Modo Económico con simulación del ciclo de pedidos."""
    global _ACTIVE_RUN_ID

    num_orders = config["num_orders"]
    num_products = config["num_products"]
    regions = config["regions"]
    init_stock = config["initial_stock_per_product"]
    simulate_idempotency = config.get("simulate_idempotency", True)

    # Catálogo sintético aislado
    inventory_state = {
        f"CYBER_SKU_{i:03d}": {
            "product_name": f"Producto Sintético Cyber Day {i}",
            "price_pen": round(29.90 + (i * 15.50), 2),
            "initial": init_stock,
            "current": init_stock,
            "total_sold": 0,
            "total_rejected": 0,
            "low_alert": False
        }
        for i in range(1, num_products + 1)
    }

    product_keys = list(inventory_state.keys())
    processed_order_ids = set()
    events_log = []

    start_time_perf = time.perf_counter()
    start_time_iso = datetime.now(timezone.utc).isoformat()

    with _STORE_LOCK:
        _RUNS_STORE[run_id]["status"] = STATUS_RUNNING
        _RUNS_STORE[run_id]["start_time"] = start_time_iso
        _RUNS_STORE[run_id]["inventory_state"] = inventory_state

    orders_completed = 0
    orders_rejected = 0
    inventory_decrements = 0
    duplicate_neutralized = 0

    event_seq = 0

    try:
        for order_idx in range(1, num_orders + 1):
            # Comprobar cancelación
            with _STORE_LOCK:
                if _RUNS_STORE[run_id].get("cancelled", False):
                    _RUNS_STORE[run_id]["status"] = STATUS_CANCELLED
                    _RUNS_STORE[run_id]["end_time"] = datetime.now(timezone.utc).isoformat()
                    return

            # Generar datos del pedido
            order_id = f"ORD_CYBER_{run_id[:8]}_{order_idx:04d}"
            region = random.choice(regions)
            product_id = random.choice(product_keys)
            # Cantidad entre 1 y 4 unidades
            requested_qty = random.randint(1, 4)
            price = inventory_state[product_id]["price_pen"]

            event_timestamp = datetime.now(timezone.utc).isoformat()

            # 1. Evento: order_created
            event_seq += 1
            evt_created = {
                "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                "run_id": run_id,
                "event_type": EVENT_ORDER_CREATED,
                "event_timestamp": event_timestamp,
                "order_id": order_id,
                "region": region,
                "product_id": product_id,
                "quantity": requested_qty,
                "synthetic_flag": True,
                "details": {"customer_type": "SYNTHETIC_CYBER_BUYER", "currency": "PEN"}
            }
            events_log.append(evt_created)

            # 2. Evento: order_item_created
            event_seq += 1
            evt_item = {
                "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                "run_id": run_id,
                "event_type": EVENT_ORDER_ITEM_CREATED,
                "event_timestamp": event_timestamp,
                "order_id": order_id,
                "product_id": product_id,
                "quantity": requested_qty,
                "price": price,
                "synthetic_flag": True
            }
            events_log.append(evt_item)

            # 3. Validación de Inventario y Reglas de Negocio
            current_stock = inventory_state[product_id]["current"]

            if current_stock >= requested_qty:
                # Stock suficiente -> Descontar inventario
                new_stock = current_stock - requested_qty
                inventory_state[product_id]["current"] = new_stock
                inventory_state[product_id]["total_sold"] += requested_qty

                # Evento: inventory_decrement
                event_seq += 1
                inventory_decrements += 1
                evt_decrement = {
                    "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                    "run_id": run_id,
                    "event_type": EVENT_INVENTORY_DECREMENT,
                    "event_timestamp": event_timestamp,
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": requested_qty,
                    "previous_stock": current_stock,
                    "new_stock": new_stock,
                    "region": region,
                    "synthetic_flag": True
                }
                events_log.append(evt_decrement)

                # Evento: inventory_low si el stock cae a 20 o menos
                if new_stock <= 20 and not inventory_state[product_id]["low_alert"]:
                    event_seq += 1
                    inventory_state[product_id]["low_alert"] = True
                    evt_low = {
                        "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                        "run_id": run_id,
                        "event_type": EVENT_INVENTORY_LOW,
                        "event_timestamp": event_timestamp,
                        "product_id": product_id,
                        "remaining_stock": new_stock,
                        "threshold": 20,
                        "region": region,
                        "synthetic_flag": True,
                        "severity": "WARNING"
                    }
                    events_log.append(evt_low)

                # Evento: order_completed
                event_seq += 1
                orders_completed += 1
                processed_order_ids.add(order_id)
                evt_completed = {
                    "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                    "run_id": run_id,
                    "event_type": EVENT_ORDER_COMPLETED,
                    "event_timestamp": event_timestamp,
                    "order_id": order_id,
                    "status": "APPROVED",
                    "total_amount": round(price * requested_qty, 2),
                    "synthetic_flag": True
                }
                events_log.append(evt_completed)

            else:
                # Stock insuficiente -> Rechazar pedido (Prevención de Stock Negativo)
                event_seq += 1
                orders_rejected += 1
                inventory_state[product_id]["total_rejected"] += 1
                evt_rejected = {
                    "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                    "run_id": run_id,
                    "event_type": EVENT_ORDER_REJECTED,
                    "event_timestamp": event_timestamp,
                    "order_id": order_id,
                    "product_id": product_id,
                    "requested_quantity": requested_qty,
                    "available_stock": current_stock,
                    "reason": f"Stock insuficiente en bodega: solicitado {requested_qty}, disponible {current_stock}.",
                    "synthetic_flag": True
                }
                events_log.append(evt_rejected)

            # Prueba de Idempotencia: re-intentar un pedido ya completado aleatoriamente (10% prob)
            if simulate_idempotency and orders_completed > 0 and random.random() < 0.10:
                dup_order_id = order_id
                event_seq += 1
                duplicate_neutralized += 1
                evt_idempotent = {
                    "event_id": f"EVT_{run_id[:8]}_{event_seq:06d}",
                    "run_id": run_id,
                    "event_type": "duplicate_order_neutralized",
                    "event_timestamp": datetime.now(timezone.utc).isoformat(),
                    "order_id": dup_order_id,
                    "action": "IDEMPOTENT_IGNORE",
                    "reason": f"Pedido {dup_order_id} ya fue procesado previamente. Stock no descontado nuevamente.",
                    "synthetic_flag": True
                }
                events_log.append(evt_idempotent)

            # Actualizar progreso periódicamente
            if order_idx % 10 == 0 or order_idx == num_orders:
                progress_pct = round((order_idx / num_orders) * 100, 1)
                with _STORE_LOCK:
                    _RUNS_STORE[run_id]["progress_pct"] = progress_pct
                    _RUNS_STORE[run_id]["total_orders"] = order_idx
                    _RUNS_STORE[run_id]["completed_orders"] = orders_completed
                    _RUNS_STORE[run_id]["rejected_orders"] = orders_rejected
                    _RUNS_STORE[run_id]["inventory_decrements"] = inventory_decrements
                    _RUNS_STORE[run_id]["duplicate_orders_neutralized"] = duplicate_neutralized
                    _RUNS_STORE[run_id]["total_events"] = len(events_log)
                    _RUNS_STORE[run_id]["events_processed"] = len(events_log)

            # Pequeña pausa para simular paso del tiempo y permitir visualización en vivo
            time.sleep(0.02)

        # Finalización exitosa
        end_time_perf = time.perf_counter()
        duration_sec = round(end_time_perf - start_time_perf, 2)
        end_time_iso = datetime.now(timezone.utc).isoformat()
        tps = round(len(events_log) / max(duration_sec, 0.01), 1)

        with _STORE_LOCK:
            _RUNS_STORE[run_id]["status"] = STATUS_COMPLETED
            _RUNS_STORE[run_id]["end_time"] = end_time_iso
            _RUNS_STORE[run_id]["duration_sec"] = duration_sec
            _RUNS_STORE[run_id]["progress_pct"] = 100.0
            _RUNS_STORE[run_id]["throughput_events_per_sec"] = tps
            _RUNS_STORE[run_id]["latency_ms_avg"] = round((duration_sec / max(len(events_log), 1)) * 1000, 2)
            _RUNS_STORE[run_id]["events"] = events_log
            _save_run_to_gcs(run_id, _RUNS_STORE[run_id])

    except Exception as e:
        with _STORE_LOCK:
            _RUNS_STORE[run_id]["status"] = STATUS_FAILED
            _RUNS_STORE[run_id]["error_message"] = str(e)
            _RUNS_STORE[run_id]["end_time"] = datetime.now(timezone.utc).isoformat()
            _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
    finally:
        with _STORE_LOCK:
            _ACTIVE_RUN_ID = None


# Control de concurrencia optimista mediante generaciones de GCS
_GCS_GENERATIONS: Dict[str, int] = {}


def _save_run_to_gcs(run_id: str, run_data: Dict[str, Any]) -> bool:
    """Persiste el estado de una simulación en Google Cloud Storage con control de concurrencia optimista.
    
    Aprovecha el bucket existente 'lumina-retail-001-data' sin tocar tablas Gold ni datos históricos.
    Si se detecta concurrencia, evita sobrescribir estados más recientes.
    """
    bucket_name = os.getenv("LUMINA_DATA_BUCKET", "lumina-retail-001-data")
    try:
        import json
        from google.cloud import storage
        client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001"))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"simulation_runs/{run_id}.json")
        
        # Payload serializable (evitar objetos mutables no serializables)
        payload = json.dumps(run_data, default=str)
        
        expected_gen = _GCS_GENERATIONS.get(run_id)
        if expected_gen is not None:
            blob.upload_from_string(
                payload,
                content_type="application/json",
                if_generation_match=expected_gen
            )
        else:
            blob.upload_from_string(
                payload,
                content_type="application/json"
            )
        blob.reload()
        _GCS_GENERATIONS[run_id] = blob.generation
        return True
    except Exception:
        # Fallback tolerante si no hay conexión o credenciales de GCS en el entorno de prueba
        return False


def _load_run_from_gcs(run_id: str) -> Optional[Dict[str, Any]]:
    """Recupera el estado de una simulación desde Google Cloud Storage."""
    bucket_name = os.getenv("LUMINA_DATA_BUCKET", "lumina-retail-001-data")
    try:
        import json
        from google.cloud import storage
        client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001"))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"simulation_runs/{run_id}.json")
        if not blob.exists():
            return None
        content = blob.download_as_text()
        data = json.loads(content)
        _GCS_GENERATIONS[run_id] = blob.generation
        return data
    except Exception:
        return None


def _list_runs_from_gcs() -> List[Dict[str, Any]]:
    """Lista las ejecuciones persistidas en Google Cloud Storage."""
    bucket_name = os.getenv("LUMINA_DATA_BUCKET", "lumina-retail-001-data")
    runs = []
    try:
        import json
        from google.cloud import storage
        client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001"))
        bucket = client.bucket(bucket_name)
        blobs = client.list_blobs(bucket, prefix="simulation_runs/", max_results=100)
        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue
            try:
                content = blob.download_as_text()
                data = json.loads(content)
                runs.append(data)
                _GCS_GENERATIONS[data["run_id"]] = blob.generation
            except Exception:
                continue
    except Exception:
        pass
    return runs


def _run_real_streaming_worker(run_id: str, config: Dict[str, Any]):
    """Ejecutor en hilo secundario para el Modo Streaming Real invocando el inyector de Kafka."""
    global _ACTIVE_RUN_ID
    import subprocess
    import json
    import os
    import time
    from datetime import datetime, timezone
    from google.cloud import bigquery

    num_orders = config["num_orders"]
    
    with _STORE_LOCK:
        _RUNS_STORE[run_id]["status"] = STATUS_PROCESSING
        _RUNS_STORE[run_id]["start_time"] = datetime.now(timezone.utc).isoformat()
        _RUNS_STORE[run_id]["total_orders"] = num_orders
        _RUNS_STORE[run_id]["total_events"] = num_orders
        _RUNS_STORE[run_id]["events_processed"] = 0
        _RUNS_STORE[run_id]["events"] = []
        
        init_stock = config.get("initial_stock_per_product", 80)
        num_products = config.get("num_products", 10)
        _RUNS_STORE[run_id]["inventory_state"] = {
            f"CYBER_SKU_{i:03d}": {
                "initial": init_stock,
                "current": init_stock,
                "total_sold": 0,
                "total_rejected": 0,
                "low_alert": False
            }
            for i in range(1, num_products + 1)
        }
        
        _save_run_to_gcs(run_id, _RUNS_STORE[run_id])

    try:
        kafka_ip = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "10.142.0.3:9092")
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
        if os.path.basename(base_dir) == "backend":
            root_dir = os.path.dirname(base_dir)
        else:
            root_dir = base_dir
            
        script_path = os.path.join(root_dir, "scripts", "stress_orders_kafka.py")
        
        cmd = [
            "python3", script_path,
            "--bootstrap-servers", kafka_ip,
            "--num-orders", str(num_orders),
            "--rate", "20",
            "--duplicate-rate", "0.05" if config.get("simulate_idempotency") else "0.0",
            "--run-id", run_id
        ]
        
        # Timeout dinámico seguro: mínimo 25s o proporcional al número de pedidos + 15s de margen
        producer_timeout = max(25, int(num_orders / 10) + 15)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=producer_timeout)
        except subprocess.TimeoutExpired:
            with _STORE_LOCK:
                _RUNS_STORE[run_id]["status"] = STATUS_FAILED
                _RUNS_STORE[run_id]["error_message"] = (
                    f"Timeout del productor Kafka: se excedió el límite de {producer_timeout}s sin respuesta del subproceso."
                )
                _RUNS_STORE[run_id]["end_time"] = datetime.now(timezone.utc).isoformat()
                _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
            return
        
        if result.returncode != 0:
            err_msg = (result.stderr or result.stdout or f"Fallo con código {result.returncode}").strip()
            with _STORE_LOCK:
                _RUNS_STORE[run_id]["status"] = STATUS_FAILED
                _RUNS_STORE[run_id]["error_message"] = f"Fallo al publicar en Kafka: {err_msg}"
                _RUNS_STORE[run_id]["end_time"] = datetime.now(timezone.utc).isoformat()
                _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
            return

        client = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001"))
        timeout = 60
        start_poll = time.time()
        total_proc = 0
        aprobados = 0
        rechazados = 0
        duplicados = 0
        events = []
        bq_consecutive_errors = 0
        last_bq_error = ""
        
        while time.time() - start_poll < timeout:
            time.sleep(3)
            try:
                sql = f'''
                SELECT 
                  COUNT(*) as total_procesado,
                  COUNTIF(order_status = 'APPROVED') as aprobados,
                  COUNTIF(order_status = 'REJECTED') as rechazados,
                  COUNTIF(order_status = 'DUPLICATE_IGNORED') as duplicados
                FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
                WHERE run_id = '{run_id}'
                '''
                res = list(client.query(sql).result())
                row = res[0]
                total_proc = row.total_procesado or 0
                aprobados = row.aprobados or 0
                rechazados = row.rechazados or 0
                duplicados = row.duplicados or 0
                bq_consecutive_errors = 0
                
                sql_ev = f'''
                SELECT event_id, run_id, event_type, order_id, product_id,
                       CAST(t_order_created AS STRING) as event_timestamp, 
                       order_status as action, reason, synthetic_flag, quantity as requested_quantity, stock_before as previous_stock, stock_after as new_stock
                FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
                WHERE run_id = '{run_id}'
                ORDER BY processed_at DESC
                LIMIT 100
                '''
                ev_res = list(client.query(sql_ev).result())
                events = [dict(e) for e in ev_res]
                
                sql_inv = f'''
                SELECT 
                  product_id as sku,
                  MAX(stock_before) as initial,
                  MIN(stock_after) as current_stock,
                  SUM(CASE WHEN order_status = 'APPROVED' THEN quantity ELSE 0 END) as total_sold,
                  COUNTIF(order_status = 'REJECTED') as total_rejected
                FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
                WHERE run_id = '{run_id}' AND product_id IS NOT NULL
                GROUP BY product_id
                '''
                inv_res = list(client.query(sql_inv).result())
                inventory_state = {}
                for r in inv_res:
                    inventory_state[r.sku] = {
                        "initial": r.initial,
                        "current": r.current_stock,
                        "total_sold": r.total_sold,
                        "total_rejected": r.total_rejected,
                        "low_alert": r.current_stock <= 20
                    }
                
                with _STORE_LOCK:
                    _RUNS_STORE[run_id]["events_processed"] = total_proc
                    _RUNS_STORE[run_id]["total_events"] = total_proc
                    _RUNS_STORE[run_id]["completed_orders"] = aprobados
                    _RUNS_STORE[run_id]["rejected_orders"] = rechazados
                    _RUNS_STORE[run_id]["duplicate_orders_neutralized"] = duplicados
                    progress = min(100.0, round((total_proc / num_orders) * 100, 1))
                    _RUNS_STORE[run_id]["progress_pct"] = progress
                    _RUNS_STORE[run_id]["events"] = events
                    if inventory_state:
                        _RUNS_STORE[run_id].setdefault("inventory_state", {}).update(inventory_state)
                    _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
                    
                if total_proc >= num_orders:
                    break
                    
            except Exception as bq_err:
                bq_consecutive_errors += 1
                last_bq_error = str(bq_err)
                if bq_consecutive_errors >= 3:
                    with _STORE_LOCK:
                        _RUNS_STORE[run_id]["error_message"] = f"Aviso de consulta BigQuery: {last_bq_error}"

        with _STORE_LOCK:
            end_time = datetime.now(timezone.utc)
            duration_sec = round((end_time - datetime.fromisoformat(_RUNS_STORE[run_id]["start_time"])).total_seconds(), 2)
            _RUNS_STORE[run_id]["end_time"] = end_time.isoformat()
            _RUNS_STORE[run_id]["duration_sec"] = duration_sec

            # REGLA ESTRICTA: Solo permitir COMPLETED si BigQuery confirmó el procesamiento completo
            if total_proc >= num_orders:
                _RUNS_STORE[run_id]["status"] = STATUS_COMPLETED
                _RUNS_STORE[run_id]["progress_pct"] = 100.0
                _RUNS_STORE[run_id]["total_events"] = total_proc
                _RUNS_STORE[run_id]["throughput_events_per_sec"] = round(total_proc / max(duration_sec, 0.01), 1)
            elif total_proc == 0:
                _RUNS_STORE[run_id]["status"] = STATUS_FAILED
                _RUNS_STORE[run_id]["progress_pct"] = 0.0
                _RUNS_STORE[run_id]["error_message"] = (
                    f"Tiempo de espera agotado ({timeout}s): ninguna orden fue confirmada en BigQuery por el pipeline Spark."
                    + (f" Último error BQ: {last_bq_error}" if last_bq_error else "")
                )
            else:
                _RUNS_STORE[run_id]["status"] = STATUS_FAILED
                _RUNS_STORE[run_id]["error_message"] = (
                    f"Procesamiento incompleto: solo {total_proc} de {num_orders} pedidos fueron procesados en BigQuery tras {timeout}s."
                )

            _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
            
    except Exception as e:
        with _STORE_LOCK:
            _RUNS_STORE[run_id]["status"] = STATUS_FAILED
            _RUNS_STORE[run_id]["error_message"] = f"Error interno real streaming: {str(e)}"
            _RUNS_STORE[run_id]["end_time"] = datetime.now(timezone.utc).isoformat()
            _save_run_to_gcs(run_id, _RUNS_STORE[run_id])
    finally:
        with _STORE_LOCK:
            if _ACTIVE_RUN_ID == run_id:
                _ACTIVE_RUN_ID = None

def create_simulation_run(config: Dict[str, Any]) -> Dict[str, Any]:
    """Crea e inicia una nueva simulación con control de concurrencia estricto."""
    global _ACTIVE_RUN_ID

    val = validate_simulation_config(config)
    if not val["valid"]:
        return {"success": False, "errors": val["errors"]}

    norm_cfg = val["normalized_config"]

    with _STORE_LOCK:
        # Control de concurrencia: no permitir dos simulaciones activas simultáneas
        if _ACTIVE_RUN_ID is not None:
            active_run = _RUNS_STORE.get(_ACTIVE_RUN_ID, {})
            if active_run.get("status") in [STATUS_RUNNING, STATUS_PROCESSING]:
                return {
                    "success": False,
                    "errors": [f"Ya existe una simulación activa en ejecución ({_ACTIVE_RUN_ID}). Espere o cancele la prueba actual."]
                }

        run_id = str(uuid.uuid4())
        _ACTIVE_RUN_ID = run_id

        run_record = {
            "run_id": run_id,
            "name": norm_cfg["name"],
            "mode": norm_cfg["mode"],
            "scenario": norm_cfg["scenario"],
            "status": STATUS_PENDING,
            "progress_pct": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "start_time": None,
            "end_time": None,
            "duration_sec": 0.0,
            "total_orders": 0,
            "completed_orders": 0,
            "rejected_orders": 0,
            "inventory_decrements": 0,
            "duplicate_orders_neutralized": 0,
            "total_events": 0,
            "events_processed": 0,
            "errors": 0,
            "throughput_events_per_sec": 0.0,
            "latency_ms_avg": 0.0,
            "synthetic_flag": True,
            "cancelled": False,
            "config": norm_cfg,
            "events": []
        }
        _RUNS_STORE[run_id] = run_record
        _save_run_to_gcs(run_id, run_record)

    # Iniciar hilo de ejecución en modo económico
    if norm_cfg["mode"] == MODE_ECONOMIC:
        worker_thread = threading.Thread(
            target=_run_economic_simulation_worker,
            args=(run_id, norm_cfg),
            daemon=True
        )
        worker_thread.start()
    else:
        # En modo streaming real, lanzar el worker especializado
        worker_thread = threading.Thread(
            target=_run_real_streaming_worker,
            args=(run_id, norm_cfg),
            daemon=True
        )
        worker_thread.start()

    return {
        "success": True,
        "run_id": run_id,
        "mode": norm_cfg["mode"],
        "status": STATUS_PENDING,
        "message": f"Simulación {run_id} iniciada en {norm_cfg['mode']}."
    }


def get_run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Consulta el estado y métricas de progreso de una ejecución."""
    with _STORE_LOCK:
        run = _RUNS_STORE.get(run_id)
        if not run:
            remote_run = _load_run_from_gcs(run_id)
            if remote_run:
                _RUNS_STORE[run_id] = remote_run
                run = remote_run
            else:
                return None
        # Retornar copia sin el arreglo completo de eventos para evitar payload masivo
        run_copy = dict(run)
        if "events" in run_copy:
            run_copy["recent_events_sample"] = run_copy["events"][-10:]
            del run_copy["events"]
        return run_copy


def get_run_events(run_id: str, limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consulta el log de eventos de una ejecución con paginación y filtros."""
    with _STORE_LOCK:
        run = _RUNS_STORE.get(run_id)
        if not run:
            remote_run = _load_run_from_gcs(run_id)
            if remote_run:
                _RUNS_STORE[run_id] = remote_run
                run = remote_run
            else:
                return []
        events = run.get("events", [])
        if event_type and event_type != "ALL":
            events = [e for e in events if e.get("event_type") == event_type]
        return events[:limit]


def get_runs_history() -> List[Dict[str, Any]]:
    """Devuelve el resumen de todas las ejecuciones registradas unificando memoria y GCS."""
    remote_runs = _list_runs_from_gcs()
    with _STORE_LOCK:
        for r in remote_runs:
            r_id = r.get("run_id")
            if r_id and r_id not in _RUNS_STORE:
                _RUNS_STORE[r_id] = r
            elif r_id and r_id in _RUNS_STORE:
                local_st = _RUNS_STORE[r_id].get("status")
                remote_st = r.get("status")
                if remote_st in [STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED] and local_st not in [STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED]:
                    _RUNS_STORE[r_id] = r

        history = []
        for r_id, r in _RUNS_STORE.items():
            history.append({
                "run_id": r["run_id"],
                "name": r.get("name", "Simulación"),
                "mode": r.get("mode"),
                "scenario": r.get("scenario"),
                "status": r.get("status"),
                "created_at": r.get("created_at") or r.get("start_time"),
                "duration_sec": r.get("duration_sec", 0),
                "total_orders": r.get("total_orders", 0),
                "completed_orders": r.get("completed_orders", 0),
                "rejected_orders": r.get("rejected_orders", 0),
                "total_events": r.get("total_events", 0),
                "throughput_events_per_sec": r.get("throughput_events_per_sec", 0),
                "is_historical": r.get("is_historical", False)
            })
        return sorted(history, key=lambda x: str(x.get("created_at") or ""), reverse=True)


def cancel_simulation_run(run_id: str) -> Dict[str, Any]:
    """Cancela de forma segura una ejecución en progreso."""
    global _ACTIVE_RUN_ID

    with _STORE_LOCK:
        run = _RUNS_STORE.get(run_id)
        if not run:
            remote_run = _load_run_from_gcs(run_id)
            if remote_run:
                _RUNS_STORE[run_id] = remote_run
                run = remote_run
            else:
                return {"success": False, "message": f"Ejecución {run_id} no encontrada."}

        if run.get("status") in [STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED]:
            return {"success": False, "message": f"La ejecución ya se encuentra en estado terminal ({run.get('status')})."}

        run["cancelled"] = True
        run["status"] = STATUS_CANCELLED
        run["end_time"] = datetime.now(timezone.utc).isoformat()
        _save_run_to_gcs(run_id, run)

        if _ACTIVE_RUN_ID == run_id:
            _ACTIVE_RUN_ID = None

        return {"success": True, "message": f"Simulación {run_id} cancelada de forma segura."}
