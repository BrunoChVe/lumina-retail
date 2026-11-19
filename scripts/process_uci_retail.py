import os
from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "data" / "uci_online_retail.csv"
OUTPUT_DIR = BASE_DIR / "data" / "silver" / "uci_online_retail"
OUTPUT_PARQUET = OUTPUT_DIR / "uci_sales_silver.parquet"


def process_uci_retail():
    print(f"Leyendo dataset bruto: {INPUT_CSV}")
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {INPUT_CSV}")

    df = pd.read_csv(
        INPUT_CSV,
        dtype={
            "InvoiceNo": str,
            "StockCode": str,
            "Description": str,
            "CustomerID": str,
            "Country": str,
        },
    )

    total_rows = len(df)
    print(f"Total registros leídos: {total_rows:,}")

    # 1. Auditoría de duplicados exactos
    raw_duplicates = df.duplicated().sum()
    print(f"Filas con duplicados exactos en origen: {raw_duplicates:,}")

    # 2. Limpieza de strings
    for col in ["InvoiceNo", "StockCode", "Description", "Country"]:
        df[col] = df[col].astype(str).str.strip()

    df["CustomerID"] = df["CustomerID"].fillna("").astype(str).str.strip()

    # 3. Conversión de tipos
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0.0).astype(float)

    # 4. Generación de identificador de línea determinista (source_item_id)
    # Asignamos índice secuencial determinista del registro CSV (1 a 541,909)
    # garantizando trazabilidad y reproducibilidad idéntica e inmutable.
    df["record_idx"] = df.index + 1
    df["source_item_id"] = "UCI_" + df["InvoiceNo"] + "_R" + df["record_idx"].astype(str)

    # Validar que no existan duplicados en la clave de línea primaria
    assert df["source_item_id"].is_unique, "Error: source_item_id no es único"

    # 5. Clasificación operativa (ventas brutas, cancelaciones y ajustes)
    is_cancellation = df["InvoiceNo"].str.startswith("C", na=False) | (df["Quantity"] < 0)
    has_valid_price = df["UnitPrice"] > 0
    is_positive_sale = (df["Quantity"] > 0) & has_valid_price

    df["source_system"] = "uci"
    df["currency_code"] = "GBP"

    # Estado de la orden
    df["order_status"] = np.where(
        is_positive_sale,
        "Complete",
        np.where(is_cancellation, "Cancelled", "Adjusted")
    )

    df["item_status"] = np.where(
        is_positive_sale,
        "delivered",
        np.where(is_cancellation, "cancelled", "non_commercial")
    )

    # 6. Cálculo financiero en GBP (preservando registros negativos)
    df["total_line_value"] = np.round(df["Quantity"] * df["UnitPrice"], 2)

    df["gross_sales_gbp"] = np.where(is_positive_sale, df["total_line_value"], 0.0)
    df["return_sales_gbp"] = np.where((df["Quantity"] < 0) & has_valid_price, df["total_line_value"], 0.0)
    df["net_sales_gbp"] = df["gross_sales_gbp"] + df["return_sales_gbp"]

    # Asignación para fact_sales estándar
    df["product_sales"] = df["total_line_value"]
    df["freight_value"] = 0.0  # UCI no dispone de costo de flete desglosado

    df["source_order_id"] = df["InvoiceNo"]
    df["source_product_id"] = df["StockCode"]
    df["source_customer_id"] = np.where(df["CustomerID"] != "", df["CustomerID"], "ANONYMOUS")
    df["order_created_at"] = df["InvoiceDate"]

    # 7. Resumen de auditoría
    null_customers = (df["source_customer_id"] == "ANONYMOUS").sum()
    cancellations_count = is_cancellation.sum()
    gross_sales_sum = df["gross_sales_gbp"].sum()
    return_sales_sum = df["return_sales_gbp"].sum()
    net_sales_sum = df["net_sales_gbp"].sum()

    print("\n========== REPORTE DE AUDITORÍA UCI ONLINE RETAIL ==========")
    print(f"Filas leídas:                 {total_rows:,}")
    print(f"Filas con ventas brutas:       {is_positive_sale.sum():,}")
    print(f"Filas de cancelación/devol.:   {cancellations_count:,}")
    print(f"Filas con clientes nulos:     {null_customers:,} ({null_customers/total_rows*100:.2f}%)")
    print(f"Filas con duplicados en origen: {raw_duplicates:,}")
    print(f"Claves primarias únicas:       {df['source_item_id'].nunique():,} (100% único)")
    print(f"Ventas brutas (GBP):          £{gross_sales_sum:,.2f}")
    print(f"Devoluciones/reembolsos (GBP): £{abs(return_sales_sum):,.2f}")
    print(f"Ventas netas (GBP):           £{net_sales_sum:,.2f}")
    print(f"Rango temporal:                {df['order_created_at'].min()} a {df['order_created_at'].max()}")
    print("============================================================\n")

    # 8. Exportar a Parquet Silver local
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df["product_name"] = df["Description"]
    df["quantity"] = df["Quantity"]
    df["unit_price"] = df["UnitPrice"]
    df["country"] = df["Country"]

    cols_to_export = [
        "source_system",
        "source_order_id",
        "source_item_id",
        "source_customer_id",
        "source_product_id",
        "product_name",
        "order_created_at",
        "order_status",
        "item_status",
        "quantity",
        "unit_price",
        "product_sales",
        "gross_sales_gbp",
        "return_sales_gbp",
        "net_sales_gbp",
        "freight_value",
        "country",
        "currency_code",
    ]
    df[cols_to_export].to_parquet(OUTPUT_PARQUET, index=False)
    print(f"Dataset Silver generado exitosamente: {OUTPUT_PARQUET}")
    print(f"Tamaño del archivo Parquet: {OUTPUT_PARQUET.stat().st_size / (1024*1024):.2f} MB")

    return df


if __name__ == "__main__":
    process_uci_retail()
