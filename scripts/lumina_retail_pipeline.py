from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim

BUCKET = "gs://lumina-retail-001-data"

spark = SparkSession.builder.appName(
    "LuminaRetailBronzeToSilver"
).getOrCreate()

datasets = [
    "olist_customers_dataset",
    "olist_geolocation_dataset",
    "olist_order_items_dataset",
    "olist_order_payments_dataset",
    "olist_order_reviews_dataset",
    "olist_orders_dataset",
    "olist_products_dataset",
    "olist_sellers_dataset",
    "product_category_name_translation",
]

try:
    for name in datasets:
        source = f"{BUCKET}/bronze/{name}.csv"
        destination = f"{BUCKET}/silver/{name}"

        print(f"Procesando: {source}")

        df = (
            spark.read
            .option("header", True)
            .option("inferSchema", True)
            .option("mode", "PERMISSIVE")
            .csv(source)
        )

        df = df.dropna(how="all")

        for field in df.schema.fields:
            if field.dataType.simpleString() == "string":
                df = df.withColumn(field.name, trim(col(field.name)))

        rows = df.count()

        df.write.mode("overwrite").parquet(destination)

        print(f"Guardado: {destination}; filas: {rows}")

    print("Proceso Bronze a Silver finalizado.")

finally:
    spark.stop()
