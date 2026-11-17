from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, sum as spark_sum, countDistinct, avg,
    date_format, datediff, when, round as spark_round
)

BUCKET = "gs://lumina-retail-001-data"

spark = SparkSession.builder.appName("LuminaRetailGold").getOrCreate()

try:
    base = f"{BUCKET}/silver/"

    orders = spark.read.parquet(base + "olist_orders_dataset")
    items = spark.read.parquet(base + "olist_order_items_dataset")
    products = spark.read.parquet(base + "olist_products_dataset")
    translations = spark.read.parquet(
        base + "product_category_name_translation"
    )

    # Ventas por mes: importe de productos, sin confundirlo con el total pagado.
    order_sales = (
        items.groupBy("order_id")
        .agg(spark_sum("price").alias("product_sales"))
    )

    sales = (
        orders.join(order_sales, "order_id", "left")
        .withColumn("order_month", date_format(
            col("order_purchase_timestamp"), "yyyy-MM"
        ))
        .filter(col("order_month").isNotNull())
        .groupBy("order_month")
        .agg(
            countDistinct("order_id").alias("orders"),
            spark_round(spark_sum("product_sales"), 2).alias("product_sales"),
            spark_round(avg("product_sales"), 2).alias("avg_product_sales_per_order")
        )
        .orderBy("order_month")
    )

    sales.write.mode("overwrite").parquet(
        f"{BUCKET}/gold/monthly_sales"
    )

    # Ventas por categoría de producto.
    category_sales = (
        items.join(products, "product_id", "left")
        .join(translations, "product_category_name", "left")
        .groupBy("product_category_name_english")
        .agg(
            spark_round(spark_sum("price"), 2).alias("product_sales"),
            countDistinct("order_id").alias("orders"),
            countDistinct("product_id").alias("distinct_products")
        )
        .orderBy(col("product_sales").desc_nulls_last())
    )

    category_sales.write.mode("overwrite").parquet(
        f"{BUCKET}/gold/category_sales"
    )

    # Tiempo entre compra y entrega para pedidos efectivamente entregados.
    delivery = (
        orders.filter(
            (col("order_status") == "delivered")
            & col("order_purchase_timestamp").isNotNull()
            & col("order_delivered_customer_date").isNotNull()
        )
        .withColumn(
            "delivery_days",
            datediff(
                col("order_delivered_customer_date"),
                col("order_purchase_timestamp")
            )
        )
        .filter(col("delivery_days") >= 0)
        .groupBy()
        .agg(
            countDistinct("order_id").alias("delivered_orders"),
            spark_round(avg("delivery_days"), 2).alias("avg_delivery_days"),
            spark_round(
                avg(when(col("delivery_days") <= 7, 1).otherwise(0)) * 100, 2
            ).alias("delivered_within_7_days_pct")
        )
    )

    delivery.write.mode("overwrite").parquet(
        f"{BUCKET}/gold/delivery_performance"
    )

    print("=== VENTAS MENSUALES ===")
    sales.show(12, truncate=False)

    print("=== TOP 10 CATEGORÍAS ===")
    category_sales.show(10, truncate=False)

    print("=== DESEMPEÑO DE ENTREGAS ===")
    delivery.show(truncate=False)

    print("Capa Gold creada correctamente.")

finally:
    spark.stop()
