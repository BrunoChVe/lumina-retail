import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, current_timestamp, to_timestamp
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType
)

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

KAFKA_BOOTSTRAP_SERVERS = "10.142.0.3:9092"
KAFKA_TOPIC = "telemetria"

OUTPUT_PATH = (
    "gs://lumina-retail-001-data/"
    "gold/streaming/telemetria_v2/"
)

CHECKPOINT_PATH = (
    "gs://lumina-retail-001-data/"
    "checkpoints/telemetria_v2/"
)

TRIGGER_INTERVAL = "5 seconds"

# --------------------------------------------------
# ESQUEMA JSON DE KAFKA
# --------------------------------------------------

telemetry_schema = StructType([
    StructField("event_id", StringType(), True),
    StructField("product_id", StringType(), True),
    StructField("region", StringType(), True),
    StructField("stock", IntegerType(), True),
    StructField("event_type", StringType(), True),
    StructField("timestamp", StringType(), True)
])

# --------------------------------------------------
# SESIÓN SPARK
# --------------------------------------------------

spark = (
    SparkSession.builder
    .appName("RetailSmart-Telemetria-Streaming")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# --------------------------------------------------
# LECTURA DESDE KAFKA
# --------------------------------------------------

kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "latest")
    .option("failOnDataLoss", "false")
    .load()
)

# --------------------------------------------------
# TRANSFORMACIÓN JSON
# --------------------------------------------------

parsed_df = (
    kafka_df
    .selectExpr("CAST(value AS STRING) AS json_value")
    .select(
        from_json(
            col("json_value"),
            telemetry_schema
        ).alias("data")
    )
    .select("data.*")
    .withColumn(
        "event_timestamp",
        to_timestamp(col("timestamp"))
    )
    .withColumn(
        "processed_at",
        current_timestamp()
    )
)

# --------------------------------------------------
# ESCRITURA PARQUET
# --------------------------------------------------

query = (
    parsed_df.writeStream
    .format("parquet")
    .outputMode("append")
    .option("path", OUTPUT_PATH)
    .option("checkpointLocation", CHECKPOINT_PATH)
    .trigger(availableNow=True)
    .start()
)

print("RetailSmart Structured Streaming iniciado")
print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Tópico: {KAFKA_TOPIC}")
print(f"Salida: {OUTPUT_PATH}")
print(f"Checkpoint: {CHECKPOINT_PATH}")
print(f"Micro-batches: {TRIGGER_INTERVAL}")

query.awaitTermination()
