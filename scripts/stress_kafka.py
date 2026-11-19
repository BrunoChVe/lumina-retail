import argparse
import json
import logging
import time
import uuid
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("stress_kafka")


def generate_synthetic_event(test_run_id: str, seq: int) -> dict:
    """
    Genera un evento de telemetría sintético debidamente etiquetado
    para impedir la contaminación de inventarios reales.
    """
    product_idx = (seq % 10) + 1
    return {
        "event_id": f"SYNTH_{test_run_id[:8]}_{seq:08d}",
        "test_run_id": test_run_id,
        "event_type": "SYNTHETIC_CYBERDAY_STRESS",
        "product_id": f"CYBER_PROD_{product_idx:03d}",
        "region": "CYBER_TEST",
        "stock": int(50 + (seq % 100)),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def run_stage(producer, topic: str, rate: int, duration_sec: int, test_run_id: str, dry_run: bool = False, batch_flush_size: int = 100):
    logger.info(f"--- Iniciando Escenario: {rate} msgs/segundo durante {duration_sec}s ---")
    interval = 1.0 / rate
    start_time = time.perf_counter()
    end_time = start_time + duration_sec

    sent_count = 0
    confirmed_count = 0
    error_count = 0
    latencies = []
    seq = 0

    def on_send_success(record_metadata, send_time):
        nonlocal confirmed_count
        confirmed_count += 1
        lat = (time.perf_counter() - send_time) * 1000
        latencies.append(lat)

    def on_send_error(exception):
        nonlocal error_count
        error_count += 1
        logger.error(f"Error asíncrono en Kafka: {exception}")

    while time.perf_counter() < end_time:
        step_start = time.perf_counter()
        seq += 1
        payload = generate_synthetic_event(test_run_id, seq)
        payload_bytes = json.dumps(payload).encode("utf-8")

        if not dry_run and producer:
            try:
                t_send = time.perf_counter()
                future = producer.send(topic, payload_bytes)
                future.add_callback(on_send_success, t_send)
                future.add_errback(on_send_error)
                sent_count += 1

                # Vaciado por lotes para no saturar memoria del buffer de Kafka
                if sent_count % batch_flush_size == 0:
                    producer.flush()
            except Exception as e:
                error_count += 1
                logger.error(f"Fallo en cola de emisión: {e}")
        else:
            sent_count += 1
            confirmed_count += 1
            latencies.append(0.1)

        # Circuit breaker / Parada segura ante fallos sostenidos
        if sent_count > 50:
            error_rate = (error_count / sent_count) * 100
            if error_rate > 5.0:
                logger.critical(f"CIRCUIT BREAKER ACTIVADO: Tasa de error ({error_rate:.2f}%) supera el 5%. Abortando prueba.")
                if not dry_run and producer:
                    producer.flush()
                return False, sent_count, error_count, latencies

        # Control de cadencia de envío
        elapsed = time.perf_counter() - step_start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    # Vaciar cualquier mensaje restante en el búfer al finalizar el escenario
    if not dry_run and producer:
        producer.flush()

    actual_duration = time.perf_counter() - start_time
    actual_rate = sent_count / actual_duration if actual_duration > 0 else 0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    logger.info(
        f"Fin de escenario: {sent_count} emitidos | {confirmed_count} confirmados | Errores: {error_count} | "
        f"RPS real: {actual_rate:.1f} msgs/s | Latencia p95: {p95_lat:.1f} ms"
    )
    return True, sent_count, error_count, latencies


def main():
    parser = argparse.ArgumentParser(description="Prueba de estrés progresiva para Kafka (CyberDay)")
    parser.add_argument("--bootstrap-servers", default="10.142.0.3:9092", help="Servidor bootstrap de Kafka")
    parser.add_argument("--topic", default="telemetria", help="Tópico de telemetría")
    parser.add_argument("--stages", default="50,100,250,500", help="Tasas de eventos (1x, 2x, 5x, 10x) en msgs/s")
    parser.add_argument("--duration", type=int, default=60, help="Duración en segundos por escenario")
    parser.add_argument("--batch-flush", type=int, default=100, help="Tamaño de lote para flush periódico")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar en modo simulación sin emitir a la red")
    args = parser.parse_args()

    test_run_id = str(uuid.uuid4())
    logger.info(f"ID de prueba de estrés (CyberDay): {test_run_id}")
    logger.info(f"Modo Dry Run: {args.dry_run}")

    producer = None
    if not args.dry_run:
        from kafka import KafkaProducer
        logger.info(f"Conectando a broker Kafka en {args.bootstrap_servers}...")
        producer = KafkaProducer(
            bootstrap_servers=args.bootstrap_servers.split(","),
            acks=1,
            retries=2,
            request_timeout_ms=5000,
            batch_size=16384,
            linger_ms=10
        )

    stages = [int(x.strip()) for x in args.stages.split(",")]
    total_sent = 0
    total_errors = 0

    try:
        for rate in stages:
            success, sent, errs, _ = run_stage(
                producer, args.topic, rate, args.duration, test_run_id,
                dry_run=args.dry_run, batch_flush_size=args.batch_flush
            )
            total_sent += sent
            total_errors += errs
            if not success:
                logger.warning("Prueba interrumpida por circuit breaker.")
                break
            time.sleep(2)  # Cooldown entre escenarios
    except KeyboardInterrupt:
        logger.warning("Prueba abortada manualmente por el operador (Ctrl+C).")
    finally:
        if producer:
            producer.close()

    logger.info(f"Resumen final CyberDay Kafka: {total_sent} eventos procesados, {total_errors} fallos.")


if __name__ == "__main__":
    main()
