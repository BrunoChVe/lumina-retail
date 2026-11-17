from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit, current_timestamp

PROJECT = "lumina-retail-001"
BUCKET = f"gs://{PROJECT}-data"

ITEMS_PATH = f"{BUCKET}/silver/olist_order_items_dataset/"
ORDERS_PATH = f"{BUCKET}/silver/olist_orders_dataset/"
SELLERS_PATH = f"{BUCKET}/silver/olist_sellers_dataset/"
OUTPUT_PATH = f"{BUCKET}/silver/olist_order_items_enriched/"

spark = (
    SparkSession.builder
    .appName("RetailSmart-Silver-Region-Enrichment")
    .getOrCreate()
)

def require_columns(df, required, dataset_name):
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas en {dataset_name}: {missing}. "
            f"Columnas disponibles: {df.columns}"
        )

try:
    # 1. Leer los tres datasets Silver y validar sus esquemas.
    items = spark.read.parquet(ITEMS_PATH)
    orders = spark.read.parquet(ORDERS_PATH)
    sellers = spark.read.parquet(SELLERS_PATH)

    print("=== ESQUEMA: ORDER ITEMS ===")
    items.printSchema()
    print("=== ESQUEMA: ORDERS ===")
    orders.printSchema()
    print("=== ESQUEMA: SELLERS ===")
    sellers.printSchema()

    require_columns(items, ["order_id", "seller_id", "product_id"], "order_items")
    require_columns(orders, ["order_id"], "orders")
    require_columns(sellers, ["seller_id", "seller_state"], "sellers")

    # 2. Asignar macrorregión de Brasil a partir del estado del vendedor.
    state = col("seller_state")
    sellers_region = sellers.withColumn(
        "seller_region",
        when(state.isin("AC", "AP", "AM", "PA", "RO", "RR", "TO"), "Norte")
        .when(state.isin("AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"), "Nordeste")
        .when(state.isin("DF", "GO", "MT", "MS"), "Centro-Oeste")
        .when(state.isin("ES", "MG", "RJ", "SP"), "Sudeste")
        .when(state.isin("PR", "RS", "SC"), "Sul")
        .otherwise("No identificado")
    ).select("seller_id", "seller_state", "seller_region")

    # 3. Unir detalle de ítems con pedidos y región del vendedor.
    enriched = (
        items.alias("i")
        .join(orders.select("order_id").dropDuplicates(["order_id"]).alias("o"),
              on="order_id", how="left")
        .join(sellers_region.alias("s"), on="seller_id", how="left")
        .withColumn("processing_timestamp", current_timestamp())
    )

    # 4. Métricas de control antes de escribir.
    total_items = items.count()
    total_enriched = enriched.count()
    missing_region = enriched.filter(
        col("seller_region").isNull() | (col("seller_region") == "No identificado")
    ).count()

    print(f"Filas originales de order_items: {total_items}")
    print(f"Filas después del enriquecimiento: {total_enriched}")
    print(f"Filas sin región identificada: {missing_region}")

    if total_items != total_enriched:
        raise ValueError(
            "La cantidad de filas cambió después de los JOIN. "
            "Se cancela la escritura para evitar duplicados o pérdida de registros."
        )

    # 5. Escribir en una nueva ruta; no sobrescribe los Silver originales.
    (enriched.write
        .mode("overwrite")
        .parquet(OUTPUT_PATH))

    print(f"Enriquecimiento finalizado. Salida: {OUTPUT_PATH}")

finally:
    spark.stop()
