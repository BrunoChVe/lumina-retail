import os
import re
import json
import time
import subprocess
from datetime import datetime, timezone

# ==========================================
# CONFIGURACION
# ==========================================

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001")
REGION = "us-east1"
CLUSTER = "lumina-retail-spark"

DEFAULT_JOB_ID = "6b474383829944ec959c2b5958e7b7af"

VM = "lumina-kafka-vm"
ZONE = "us-east1-b"

TOPIC = "telemetria"

CHECKPOINT = (
    "gs://lumina-retail-001-data/"
    "checkpoints/telemetria_v2/"
)

OUTPUT = (
    "gs://lumina-retail-001-data/"
    "gold/streaming/telemetria_v2/"
)


def execute(command):
    t0 = time.perf_counter()
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "Command failed"
        )

    return result.stdout.strip()


def get_spark_status(job_id=None):
    target_job = job_id or DEFAULT_JOB_ID
    try:
        output = execute([
            "gcloud", "dataproc", "jobs", "describe",
            target_job,
            f"--region={REGION}",
            f"--project={PROJECT}",
            "--format=json"
        ])
        data = json.loads(output)
        state = data["status"]["state"]
        return target_job, state
    except Exception:
        # Búsqueda dinámica del job activo en el clúster
        output_list = execute([
            "gcloud", "dataproc", "jobs", "list",
            f"--region={REGION}",
            f"--project={PROJECT}",
            f"--filter=status.state=RUNNING AND placement.clusterName={CLUSTER}",
            "--format=json(reference.jobId)",
            "--limit=1"
        ])
        jobs = json.loads(output_list)
        if jobs:
            active_id = jobs[0]["reference"]["jobId"]
            return active_id, "RUNNING"
        return target_job, "NOT_FOUND"


def get_kafka_offsets():
    command = (
        "/opt/kafka/bin/kafka-get-offsets.sh "
        f"--bootstrap-server 10.142.0.3:9092 "
        f"--topic {TOPIC}"
    )

    output = execute([
        "gcloud", "compute", "ssh", VM,
        f"--zone={ZONE}",
        f"--project={PROJECT}",
        f"--command={command}"
    ])

    # Capturar todas las particiones: topic:partition:offset
    matches = re.findall(rf"{TOPIC}:(\d+):(\d+)", output)
    if not matches:
        raise RuntimeError("No se pudo obtener el offset Kafka")

    return {str(part): int(offset) for part, offset in matches}


def get_spark_offsets():
    offsets_output = execute([
        "gcloud", "storage", "ls",
        CHECKPOINT + "offsets/"
    ])

    commits_output = execute([
        "gcloud", "storage", "ls",
        CHECKPOINT + "commits/"
    ])

    def extract_batches(output):
        batches = set()
        for line in output.splitlines():
            match = re.search(r"/(\d+)$", line.strip())
            if match:
                batches.add(int(match.group(1)))
        return batches

    offset_batches = extract_batches(offsets_output)
    commit_batches = extract_batches(commits_output)
    completed_batches = offset_batches & commit_batches

    if not completed_batches:
        raise RuntimeError("No existen micro-lotes con offset y commit")

    latest_batch = max(completed_batches)
    content = execute([
        "gcloud", "storage", "cat",
        f"{CHECKPOINT}offsets/{latest_batch}"
    ])

    for line in reversed(content.splitlines()):
        try:
            data = json.loads(line)
            if TOPIC in data:
                partition_offsets = data[TOPIC]
                return latest_batch, {str(p): int(o) for p, o in partition_offsets.items()}
        except (ValueError, KeyError, TypeError):
            continue

    raise RuntimeError("No se pudo interpretar el offset confirmado")


def get_latest_parquet():
    output = execute([
        "gcloud", "storage", "ls", "-l",
        OUTPUT
    ])

    files = []
    pattern = re.compile(
        r"^\s*(\d+)\s+"
        r"(\d{4}-\d{2}-\d{2}T\S+)\s+"
        r"(gs://\S+\.parquet)"
    )

    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            files.append({
                "size": int(match.group(1)),
                "timestamp": match.group(2),
                "path": match.group(3)
            })

    if not files:
        return None

    return max(files, key=lambda item: item["timestamp"])


def main():
    t_start = time.perf_counter()
    print("=" * 55)
    print("       RETAILSMART - MONITOR DE STREAMING")
    print("=" * 55)
    print(
        "Fecha UTC:",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )

    errors = []

    try:
        job_id, status = get_spark_status()
        print(f"\n[SPARK] Job ID: {job_id}")
        print(f"[SPARK] Estado: {status}")

        if status != "RUNNING":
            errors.append(f"Spark no está RUNNING (Estado: {status})")

    except Exception as error:
        print(f"\n[SPARK] ERROR: {error}")
        errors.append("No se pudo consultar Spark")

    try:
        kafka_offsets = get_kafka_offsets()
        batch, spark_offsets = get_spark_offsets()

        print(f"\n[SPARK] Último batch confirmado: {batch}")
        print("[PARTICIONES Y LAG]")

        total_kafka = 0
        total_spark = 0

        for part, k_off in sorted(kafka_offsets.items(), key=lambda x: int(x[0])):
            s_off = spark_offsets.get(part, 0)
            p_lag = k_off - s_off
            total_kafka += k_off
            total_spark += s_off
            print(f"  Partición {part}: Kafka={k_off:,} | Spark={s_off:,} | Lag={p_lag:,}")

        lag_total = total_kafka - total_spark
        print(f"[LAG TOTAL]: {lag_total:,} eventos")

        if lag_total < 0:
            print("[LAG] ADVERTENCIA: offsets inconsistentes")
            errors.append("Offsets inconsistentes")
        elif lag_total > 0:
            print(f"[LAG] Hay {lag_total:,} mensajes pendientes de procesar")
        else:
            print("[LAG] Sin retraso de offsets (Lag = 0)")

    except Exception as error:
        print(f"\n[OFFSETS] ERROR: {error}")
        errors.append(f"Fallo comparando offsets: {error}")

    try:
        parquet = get_latest_parquet()
        if parquet:
            print("\n[GCS] Último archivo Parquet emitido:")
            print("  Fecha:", parquet["timestamp"])
            print("  Tamaño:", f"{parquet['size']:,} bytes")
            print("  Ruta:", parquet["path"])
        else:
            print("\n[GCS] No se encontraron archivos Parquet")
    except Exception as error:
        print(f"\n[GCS] ERROR: {error}")
        errors.append(f"Fallo consultando GCS: {error}")

    elapsed = time.perf_counter() - t_start
    print("\n" + "=" * 55)
    if errors:
        print("RESULTADO: REVISAR")
        for error in errors:
            print("-", error)
    else:
        print("RESULTADO: MONITOREO COMPLETADO (OK)")
    print(f"Tiempo de ejecución: {elapsed:.2f} s")
    print("=" * 55)


if __name__ == "__main__":
    main()
