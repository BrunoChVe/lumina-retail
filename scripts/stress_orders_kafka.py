"""
LUMINA RETAIL — INYECTOR DE PEDIDOS Y TELEMETRÍA A KAFKA (CYBER DAYS)
====================================================================
Componente: Generador de Carga Transaccional de Pedidos
Funcionalidades:
  1. Generación sintética aislada de pedidos (Catálogo CYBER_SKU_001 a 010)
  2. Telemetría de alta resolución (t_order_created, t_event_published)
  3. Confirmación estricta de publicación mediante callbacks (ACK)
  4. Inyección de pedidos duplicados controlados para validación de Idempotencia
  5. Cálculo riguroso de percentiles de latencia (P50, P90, P95, P99)
  6. Modos: Modo Real (Kafka) y Modo Dry Run (validación offline)
====================================================================
"""

import argparse
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [KafkaOrderProducer] %(message)s")
logger = logging.getLogger("KafkaOrderProducer")

REGIONS = ["Lima", "Norte", "Sur", "Centro", "Oriente"]
CATALOG_SKUS = [f"CYBER_SKU_{i:03d}" for i in range(1, 11)]
SKU_PRICES = {f"CYBER_SKU_{i:03d}": round(29.90 + (i * 15.50), 2) for i in range(1, 11)}


def create_order_payload(
    run_id: str,
    seq: int,
    order_id: str = None,
    product_id: str = None,
    qty: int = None,
    is_duplicate: bool = False
) -> Dict[str, Any]:
    """Crea un evento de pedido instrumentado con telemetría de latencia."""
    t_created = time.time()
    oid = order_id or f"ORD_CYBER_{run_id[:8]}_{seq:05d}"
    pid = product_id or random.choice(CATALOG_SKUS)
    quantity = qty or random.randint(1, 4)
    price = SKU_PRICES.get(pid, 49.90)
    total = round(price * quantity, 2)
    region = random.choice(REGIONS)

    return {
        "run_id": run_id,
        "event_id": f"EVT_{run_id[:8]}_{seq:06d}",
        "order_id": oid,
        "event_type": "order_created",
        "product_id": pid,
        "region": region,
        "quantity": quantity,
        "unit_price": price,
        "total_amount": total,
        "synthetic_flag": True,
        "is_duplicate_intent": is_duplicate,
        "t_order_created": t_created,
        "t_event_published": None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Calcula percentiles estadísticos P50, P90, P95, P99 sin librerías externas."""
    if not values:
        return {"avg": 0.0, "min": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    s = sorted(values)
    n = len(s)

    def pct(p):
        idx = int(round((p / 100.0) * (n - 1)))
        return round(s[min(max(idx, 0), n - 1)], 2)

    return {
        "avg": round(sum(s) / n, 2),
        "min": round(s[0], 2),
        "p50": pct(50),
        "p90": pct(90),
        "p95": pct(95),
        "p99": pct(99),
        "max": round(s[-1], 2)
    }


def run_orders_stage(
    producer,
    topic: str,
    num_orders: int,
    rate_orders_per_sec: int,
    duplicate_rate: float,
    run_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Ejecuta un escenario de inyección de pedidos a Kafka."""
    logger.info(
        f"--- Iniciando Escenario: {num_orders} pedidos a ~{rate_orders_per_sec} ops/s "
        f"(duplicados: {int(duplicate_rate * 100)}%, tópico: {topic}) ---"
    )

    interval = 1.0 / max(rate_orders_per_sec, 1)
    t_stage_start = time.perf_counter()

    published_latencies_ms = []
    sent_count = 0
    confirmed_count = 0
    error_count = 0
    duplicate_count = 0

    order_history: List[Dict[str, Any]] = []

    def on_send_success(*args):
        nonlocal confirmed_count
        confirmed_count += 1
        t_ack = time.time()
        # Buscar el float que representa t_order_created entre los argumentos
        t_order_created = None
        for a in args:
            if isinstance(a, (int, float)):
                t_order_created = a
                break
        if t_order_created is not None:
            lat_ms = (t_ack - t_order_created) * 1000.0
            published_latencies_ms.append(lat_ms)

    def on_send_error(exception):
        nonlocal error_count
        error_count += 1
        logger.error(f"Fallo de entrega en Kafka: {exception}")

    for idx in range(1, num_orders + 1):
        step_start = time.perf_counter()

        # Decidir si emitir un duplicado de un pedido anterior (Prueba de Idempotencia)
        is_dup = False
        if duplicate_rate > 0 and order_history and random.random() < duplicate_rate:
            past_order = random.choice(order_history)
            payload = create_order_payload(
                run_id=run_id,
                seq=idx,
                order_id=past_order["order_id"],
                product_id=past_order["product_id"],
                qty=past_order["quantity"],
                is_duplicate=True
            )
            is_dup = True
            duplicate_count += 1
        else:
            payload = create_order_payload(run_id=run_id, seq=idx)
            order_history.append(payload)

        payload_bytes = json.dumps(payload).encode("utf-8")
        t_create = payload["t_order_created"]

        if not dry_run and producer:
            try:
                future = producer.send(topic, key=payload["order_id"].encode("utf-8"), value=payload_bytes)
                future.add_callback(on_send_success, t_create)
                future.add_errback(on_send_error)
                sent_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Excepción emitiendo pedido {payload['order_id']}: {e}")
        else:
            # Modo Dry Run: confirmación local inmediata
            sent_count += 1
            confirmed_count += 1
            published_latencies_ms.append(random.uniform(0.5, 3.5))

        # Cadencia de envío
        elapsed = time.perf_counter() - step_start
        sleep_dur = interval - elapsed
        if sleep_dur > 0:
            time.sleep(sleep_dur)

    # Esperar confirmación de todos los mensajes pendientes
    if not dry_run and producer:
        logger.info("Esperando confirmación final (flush) de Kafka...")
        producer.flush(timeout=15)

    duration = round(time.perf_counter() - t_stage_start, 2)
    throughput = round(sent_count / max(duration, 0.01), 1)
    stats = calculate_percentiles(published_latencies_ms)

    logger.info(
        f"Fin de escenario: {sent_count} pedidos emitidos | {confirmed_count} confirmados por Kafka | "
        f"{error_count} errores | {duplicate_count} duplicados de prueba | "
        f"Throughput: {throughput} ops/s | Duración: {duration}s | "
        f"Latencia P50: {stats['p50']} ms | P95: {stats['p95']} ms | P99: {stats['p99']} ms"
    )

    return {
        "run_id": run_id,
        "num_orders": num_orders,
        "sent_count": sent_count,
        "confirmed_count": confirmed_count,
        "error_count": error_count,
        "duplicate_count": duplicate_count,
        "duration_sec": duration,
        "throughput_ops_per_sec": throughput,
        "latencies_ms": stats
    }


def check_broker_connectivity(bootstrap_servers: str, timeout_sec: float = 3.0) -> Tuple[bool, str]:
    """Valida la conectividad TCP directa a los brokers antes de inicializar KafkaProducer."""
    import socket
    brokers = [b.strip() for b in bootstrap_servers.split(",") if b.strip()]
    if not brokers:
        return False, "No se especificaron brokers válidos."
    
    last_err = ""
    for b in brokers:
        parts = b.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9092
        try:
            with socket.create_connection((host, port), timeout=timeout_sec):
                return True, f"Conexión TCP exitosa a {host}:{port}"
        except Exception as e:
            last_err = f"{host}:{port} ({e})"
    return False, f"Ningún broker respondió en el tiempo límite: {last_err}"


def main():
    default_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "10.142.0.3:9092")
    parser = argparse.ArgumentParser(description="Inyector de pedidos streaming a Kafka (LUMINA Retail)")
    parser.add_argument("--bootstrap-servers", default=default_servers, help="Brokers de Kafka")
    parser.add_argument("--topic", default="orders_stream", help="Tópico de destino")
    parser.add_argument("--num-orders", type=int, default=50, help="Cantidad de pedidos")
    parser.add_argument("--rate", type=int, default=25, help="Tasa de pedidos por segundo (TPS)")
    parser.add_argument("--duplicate-rate", type=float, default=0.10, help="Porcentaje de pedidos duplicados (0.0 a 1.0)")
    parser.add_argument("--run-id", default=None, help="Identificador único de ejecución")
    parser.add_argument("--dry-run", action="store_true", help="Simulación local sin conexión física a red")
    args = parser.parse_args()

    run_id = args.run_id or str(uuid.uuid4())
    logger.info("=" * 65)
    logger.info("  LUMINA RETAIL — INYECTOR DE PEDIDOS CYBER DAYS")
    logger.info("=" * 65)
    logger.info(f"Run ID             : {run_id}")
    logger.info(f"Bootstrap Servers  : {args.bootstrap_servers}")
    logger.info(f"Tópico             : {args.topic}")
    logger.info(f"Pedidos a emitir   : {args.num_orders}")
    logger.info(f"Tasa objetivo      : {args.rate} ops/s")
    logger.info(f"Tasa de duplicados : {int(args.duplicate_rate * 100)}%")
    logger.info(f"Modo Dry Run       : {args.dry_run}")

    producer = None
    if not args.dry_run:
        ok, msg = check_broker_connectivity(args.bootstrap_servers, timeout_sec=3.0)
        if not ok:
            logger.error(f"Fallo de conectividad previa a Kafka: {msg}")
            sys.stderr.write(f"ERROR: {msg}\n")
            sys.exit(1)

        try:
            from kafka import KafkaProducer
            logger.info("Inicializando KafkaProducer...")
            producer = KafkaProducer(
                bootstrap_servers=args.bootstrap_servers.split(","),
                acks="all",
                retries=2,
                max_block_ms=5000,
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000,
                batch_size=16384,
                linger_ms=5
            )
            logger.info("KafkaProducer conectado y listo.")
        except Exception as e:
            logger.error(f"Error fatal inicializando productor Kafka: {e}")
            sys.stderr.write(f"ERROR: Fallo inicializando KafkaProducer: {e}\n")
            sys.exit(1)

    result = run_orders_stage(
        producer=producer,
        topic=args.topic,
        num_orders=args.num_orders,
        rate_orders_per_sec=args.rate,
        duplicate_rate=args.duplicate_rate,
        run_id=run_id,
        dry_run=args.dry_run
    )

    if producer:
        producer.close()

    if result.get("error_count", 0) > 0 and result.get("confirmed_count", 0) == 0:
        logger.error(f"Fallo total: 0 de {args.num_orders} pedidos confirmados.")
        sys.stderr.write("ERROR: Todos los pedidos fallaron al enviarse a Kafka.\n")
        sys.exit(1)

    print("\n" + json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
