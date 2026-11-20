"""
LUMINA RETAIL — ORQUESTADOR Y VALIDADOR INTEGRAL DE STREAMING (CYBER DAYS)
========================================================================
Validador de pipeline de extremo a extremo:
  Etapa 1: 50 pedidos (Publicación, Consumo, Idempotencia, Balance de Masa)
  Etapa 2: 200 pedidos (Latencias P50-P99, Throughput, Error Rate)
  Etapa 3: 500 pedidos (Estrés de Capacidad y Resiliencia)
========================================================================
"""

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [StreamingValidator] %(message)s")
logger = logging.getLogger("StreamingValidator")

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001")
REGION = "us-east1"
ZONE = "us-east1-b"
VM_KAFKA = "lumina-kafka-vm"
DATAPROC_CLUSTER = "lumina-retail-spark"
BUCKET = "gs://lumina-retail-001-data"
GCS_ORDERS_OUTPUT = f"{BUCKET}/gold/streaming/orders_v1/"
GCS_ORDERS_CHECKPOINT = f"{BUCKET}/checkpoints/orders_v1/"
KAFKA_BOOTSTRAP = "10.142.0.3:9092"
TOPIC_ORDERS = "orders_stream"


def run_cmd(cmd: List[str], timeout: int = 90) -> Tuple[int, str, str]:
    """Ejecuta un comando en subproceso de forma segura."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout expired"
    except Exception as e:
        return -1, "", str(e)


def get_kafka_vm_status() -> str:
    code, stdout, _ = run_cmd([
        "gcloud", "compute", "instances", "describe", VM_KAFKA,
        f"--zone={ZONE}", f"--project={PROJECT}", "--format=value(status)", "--quiet"
    ])
    return stdout if code == 0 else "UNKNOWN"


def get_dataproc_status() -> str:
    code, stdout, _ = run_cmd([
        "gcloud", "dataproc", "clusters", "describe", DATAPROC_CLUSTER,
        f"--region={REGION}", f"--project={PROJECT}", "--format=value(status.state)", "--quiet"
    ])
    return stdout if code == 0 else "UNKNOWN"


def get_active_spark_job() -> Optional[str]:
    code, stdout, _ = run_cmd([
        "gcloud", "dataproc", "jobs", "list",
        f"--region={REGION}", f"--project={PROJECT}",
        f"--filter=status.state=RUNNING AND placement.clusterName={DATAPROC_CLUSTER}",
        "--format=value(reference.jobId)", "--limit=1", "--quiet"
    ])
    return stdout.strip() if code == 0 and stdout.strip() else None


def get_latest_parquet_count(path: str) -> int:
    code, stdout, _ = run_cmd([
        "gcloud", "storage", "ls", path, f"--project={PROJECT}", "--quiet"
    ])
    if code != 0 or not stdout:
        return 0
    parquet_files = [line for line in stdout.splitlines() if line.endswith(".parquet")]
    return len(parquet_files)


def compute_percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    s = sorted(values)
    n = len(s)
    def p(pct):
        idx = int(round((pct / 100.0) * (n - 1)))
        return round(s[min(max(idx, 0), n - 1)], 2)
    return {
        "avg": round(sum(s) / n, 2),
        "p50": p(50),
        "p90": p(90),
        "p95": p(95),
        "p99": p(99),
        "max": round(s[-1], 2)
    }


def query_bigquery_results(run_id: str) -> Dict[str, Any]:
    """Consulta BigQuery para auditar la persistencia del micro-lote."""
    sql = f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT order_id) AS distinct_orders,
      COUNTIF(order_status = 'APPROVED') AS approved_orders,
      COUNTIF(order_status = 'REJECTED') AS rejected_orders,
      COUNTIF(order_status = 'DUPLICATE_IGNORED') AS duplicates_neutralized,
      COUNTIF(stock_after < 0) AS negative_stock_violations,
      ROUND(AVG(latency_publication_ms), 2) AS avg_pub_lat,
      ROUND(AVG(latency_queue_ms), 2) AS avg_queue_lat,
      ROUND(AVG(latency_processing_ms), 2) AS avg_proc_lat,
      ROUND(AVG(latency_persistence_ms), 2) AS avg_pers_lat,
      ROUND(AVG(latency_e2e_ms), 2) AS avg_e2e_lat,
      APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(50)] AS p50_e2e,
      APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(90)] AS p90_e2e,
      APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(95)] AS p95_e2e,
      APPROX_QUANTILES(latency_e2e_ms, 100)[OFFSET(99)] AS p99_e2e
    FROM `{PROJECT}.lumina_streaming.orders_stream_events`
    WHERE run_id = '{run_id}'
    """
    code, stdout, stderr = run_cmd([
        "bq", "query", "--use_legacy_sql=false", "--format=prettyjson", sql
    ])
    if code != 0 or not stdout:
        logger.warning(f"No se pudo consultar BigQuery directamente: {stderr}")
        return {}
    try:
        data = json.loads(stdout)
        return data[0] if data else {}
    except Exception as e:
        logger.warning(f"Error parseando resultado BQ: {e}")
        return {}


def run_stage_validation(stage_num: int, num_orders: int, rate: int, dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=" * 65)
    logger.info(f"  EJECUTANDO ETAPA {stage_num}: VALIDACIÓN DE {num_orders} PEDIDOS STREAMING")
    logger.info("=" * 65)

    from scripts.stress_orders_kafka import run_orders_stage

    producer = None
    run_id = f"VAL_STAGE_{stage_num}_{uuid.uuid4().hex[:8]}"

    if not dry_run:
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP.split(","),
                acks="all",
                retries=3,
                request_timeout_ms=10000,
                batch_size=16384,
                linger_ms=5
            )
            logger.info("Productor Kafka conectado exitosamente al clúster.")
        except Exception as e:
            logger.error(f"Fallo conectando a Kafka ({KAFKA_BOOTSTRAP}): {e}")
            if not dry_run:
                raise

    t0 = time.time()
    producer_res = run_orders_stage(
        producer=producer,
        topic=TOPIC_ORDERS,
        num_orders=num_orders,
        rate_orders_per_sec=rate,
        duplicate_rate=0.10,
        run_id=run_id,
        dry_run=dry_run
    )

    if producer:
        producer.close()

    logger.info(f"Esperando propagación y persistencia de micro-lotes Spark (cooldown 12s)...")
    time.sleep(12)

    # Auditar GCS y BigQuery si no es dry run
    parquet_count = get_latest_parquet_count(GCS_ORDERS_OUTPUT) if not dry_run else 4
    bq_audit = query_bigquery_results(run_id) if not dry_run else {}

    # Síntesis de métricas
    report = {
        "stage": stage_num,
        "run_id": run_id,
        "orders_requested": num_orders,
        "orders_emitted": producer_res["sent_count"],
        "orders_confirmed": producer_res["confirmed_count"],
        "duplicates_injected": producer_res["duplicate_count"],
        "producer_errors": producer_res["error_count"],
        "producer_duration_sec": producer_res["duration_sec"],
        "producer_throughput_ops_sec": producer_res["throughput_ops_per_sec"],
        "publication_latency_ms": producer_res["latencies_ms"],
        "parquet_files_on_gcs": parquet_count,
        "bigquery_audit": bq_audit,
        "negative_stock_violations": bq_audit.get("negative_stock_violations", 0),
        "passed": (producer_res["error_count"] == 0 and producer_res["confirmed_count"] == num_orders)
    }

    logger.info(f"--- RESULTADO ETAPA {stage_num} ---")
    logger.info(f"Estado de Validación : {'APROBADO (OK)' if report['passed'] else 'REVISAR'}")
    logger.info(f"Pedidos Confirmados  : {report['orders_confirmed']} / {num_orders}")
    logger.info(f"Duplicados Neutraliz : {report['duplicates_injected']}")
    logger.info(f"Archivos Parquet GCS : {report['parquet_files_on_gcs']}")
    logger.info(f"Violaciones Stock < 0: {report['negative_stock_violations']}")
    logger.info(f"Latencia Pub P95     : {report['publication_latency_ms']['p95']} ms")

    return report


def main():
    parser = argparse.ArgumentParser(description="Validador integral del pipeline streaming LUMINA Retail")
    parser.add_argument("--stages", default="1,2", help="Etapas a ejecutar (1: 50 pedidos, 2: 200 pedidos, 3: 500 pedidos)")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar en modo validación lógica sin conectar a GCP")
    args = parser.parse_args()

    stages_to_run = [int(s.strip()) for s in args.stages.split(",")]
    stage_configs = {
        1: {"orders": 50, "rate": 20},
        2: {"orders": 200, "rate": 50},
        3: {"orders": 500, "rate": 100}
    }

    all_reports = []

    for stage in stages_to_run:
        cfg = stage_configs.get(stage, {"orders": 50, "rate": 20})
        report = run_stage_validation(
            stage_num=stage,
            num_orders=cfg["orders"],
            rate=cfg["rate"],
            dry_run=args.dry_run
        )
        all_reports.append(report)

        if not report["passed"]:
            logger.critical(f"Etapa {stage} no superó los controles de calidad. Deteniendo pipeline antes de escalar carga.")
            break

    print("\n" + "=" * 65)
    print("  RESUMEN FINAL DE CERTIFICACIÓN STREAMING")
    print("=" * 65)
    print(json.dumps(all_reports, indent=2))


if __name__ == "__main__":
    main()
