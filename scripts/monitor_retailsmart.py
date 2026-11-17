import re
import json
import subprocess
from datetime import datetime, timezone

# ==========================================
# CONFIGURACION
# ==========================================

PROJECT = "lumina-retail-001"
REGION = "us-east1"
CLUSTER = "lumina-retail-spark"

JOB_ID = "0dd5dd1c6a8541ae840e9655bb940f7d"

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


def get_spark_status():
    output = execute([
        "gcloud", "dataproc", "jobs", "describe",
        JOB_ID,
        f"--region={REGION}",
        f"--project={PROJECT}",
        "--format=json"
    ])

    data = json.loads(output)
    return data["status"]["state"]


def get_kafka_offset():
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

    match = re.search(
        rf"{TOPIC}:\d+:(\d+)",
        output
    )

    if not match:
        raise RuntimeError("No se pudo obtener el offset Kafka")

    return int(match.group(1))


def get_spark_offset():
    # Obtener offsets registrados
    offsets_output = execute([
        "gcloud", "storage", "ls",
        CHECKPOINT + "offsets/"
    ])

    # Obtener commits confirmados
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

    # Solo considerar micro-lotes con offset y commit
    completed_batches = offset_batches & commit_batches

    if not completed_batches:
        raise RuntimeError(
            "No existen micro-lotes con offset y commit"
        )

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

                return latest_batch, int(
                    partition_offsets["0"]
                )

        except (ValueError, KeyError, TypeError):
            continue

    raise RuntimeError(
        "No se pudo interpretar el offset confirmado"
    )

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

    return max(
        files,
        key=lambda item: item["timestamp"]
    )


def main():
    print("=" * 55)
    print("       RETAILSMART - MONITOR DE STREAMING")
    print("=" * 55)
    print(
        "Fecha UTC:",
        datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    errors = []

    try:
        status = get_spark_status()
        print(f"\n[SPARK] Estado: {status}")

        if status != "RUNNING":
            errors.append("Spark no está RUNNING")

    except Exception as error:
        print(f"\n[SPARK] ERROR: {error}")
        errors.append("No se pudo consultar Spark")

    try:
        kafka_offset = get_kafka_offset()
        batch, spark_offset = get_spark_offset()

        lag = kafka_offset - spark_offset

        print(f"\n[KAFKA] Último offset: {kafka_offset}")
        print(f"[SPARK] Último batch: {batch}")
        print(f"[SPARK] Offset confirmado: {spark_offset}")
        print(f"[LAG] Diferencia: {lag}")

        if lag < 0:
            print("[LAG] ADVERTENCIA: offsets inconsistentes")
            errors.append("Offsets inconsistentes")
        elif lag > 0:
            print("[LAG] Hay mensajes pendientes")
        else:
            print("[LAG] Sin retraso de offsets")

    except Exception as error:
        print(f"\n[OFFSETS] ERROR: {error}")
        errors.append("No se pudieron comparar offsets")

    try:
        parquet = get_latest_parquet()

        if parquet:
            print("\n[GCS] Último archivo Parquet:")
            print("Fecha:", parquet["timestamp"])
            print("Tamaño:", parquet["size"], "bytes")
            print("Ruta:", parquet["path"])
        else:
            print("\n[GCS] No se encontraron archivos Parquet")

    except Exception as error:
        print(f"\n[GCS] ERROR: {error}")
        errors.append("No se pudo consultar GCS")

    print("\n" + "=" * 55)

    if errors:
        print("RESULTADO: REVISAR")
        for error in errors:
            print("-", error)
    else:
        print("RESULTADO: MONITOREO COMPLETADO")

    print("=" * 55)


if __name__ == "__main__":
    main()
