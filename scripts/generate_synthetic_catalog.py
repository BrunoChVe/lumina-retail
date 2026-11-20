import json
import random
import uuid
import os
import sys
from datetime import datetime, timezone
from google.cloud import bigquery
from google.cloud import storage

# Semilla reproducible
random.seed(42)

CATEGORIES = [
    "Electrónica", "Computación", "Electrodomésticos", "Hogar", 
    "Moda", "Belleza", "Deportes", "Accesorios"
]

BRANDS = ["LuminaTech", "LuminaHome", "LuminaStyle", "LuminaFit", "Generic"]

PRODUCTS = []
INVENTORY = []

def generate_catalog():
    print("Generando catálogo sintético...")
    for i in range(1, 101):
        sku = f"CYBER_SKU_{i:03d}"
        category = random.choice(CATEGORIES)
        brand = random.choice(BRANDS)
        
        # Generar nombre realista
        base_names = {
            "Electrónica": ["Smart TV 4K", "Auriculares Inalámbricos", "Barra de Sonido", "Cámara Digital"],
            "Computación": ["Laptop Pro", "Monitor 27''", "Teclado Mecánico", "Ratón Inalámbrico"],
            "Electrodomésticos": ["Refrigeradora", "Microondas", "Batidora", "Licuadora"],
            "Hogar": ["Set de Sábanas", "Lámpara LED", "Almohada Viscoelástica", "Organizador"],
            "Moda": ["Chaqueta de Invierno", "Zapatillas Urbanas", "Pantalón Denim", "Camisa Casual"],
            "Belleza": ["Set de Skincare", "Perfume", "Secadora de Cabello", "Plancha de Cabello"],
            "Deportes": ["Bicicleta Estática", "Set de Mancuernas", "Esterilla de Yoga", "Banda Elástica"],
            "Accesorios": ["Reloj Inteligente", "Mochila", "Gafas de Sol", "Billetera"]
        }
        name_prefix = random.choice(base_names[category])
        product_name = f"{name_prefix} {brand} Modelo {random.randint(100, 999)}"
        
        unit_cost = round(random.uniform(10.0, 500.0), 2)
        margin = random.uniform(1.2, 2.0)
        unit_price = round(unit_cost * margin, 2)
        
        warehouse_id = random.choice(["WH_LIMA", "WH_NORTE", "WH_SUR"])
        
        # Definir nivel de stock
        stock_level = random.choices(
            ["Alto", "Medio", "Bajo", "Agotado"],
            weights=[40, 40, 15, 5],
            k=1
        )[0]
        
        if stock_level == "Alto":
            initial_stock = random.randint(100, 300)
        elif stock_level == "Medio":
            initial_stock = random.randint(30, 99)
        elif stock_level == "Bajo":
            initial_stock = random.randint(1, 29)
        else:
            initial_stock = 0
            
        reorder_point = 20
        supplier_id = f"SUP_{random.randint(1000, 9999)}"
        
        product = {
            "sku": sku,
            "product_id": str(uuid.uuid4()),
            "product_name": product_name,
            "category": category,
            "brand": brand,
            "unit_price": unit_price,
            "unit_cost": unit_cost,
            "warehouse_id": warehouse_id,
            "reorder_point": reorder_point,
            "supplier_id": supplier_id,
            "active": True
        }
        PRODUCTS.append(product)
        
        now_iso = datetime.now(timezone.utc).isoformat()
        inventory_record = {
            "inventory_id": str(uuid.uuid4()),
            "sku": sku,
            "warehouse_id": warehouse_id,
            "initial_stock": initial_stock,
            "available_stock": initial_stock,
            "reserved_stock": 0,
            "run_id": "BASE",
            "created_at": now_iso,
            "updated_at": now_iso
        }
        INVENTORY.append(inventory_record)

def upload_to_gcs_and_bq():
    project_id = "lumina-retail-001"
    bucket_name = "lumina-retail-001-data"
    dataset_id = "lumina_sandbox"
    
    storage_client = storage.Client(project=project_id)
    bq_client = bigquery.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    
    # Upload Products
    products_blob = bucket.blob("reference/products/catalog.jsonl")
    products_jsonl = "\n".join([json.dumps(p) for p in PRODUCTS])
    products_blob.upload_from_string(products_jsonl, content_type="application/jsonl")
    print(f"Subido: gs://{bucket_name}/reference/products/catalog.jsonl")
    
    # Upload Inventory
    inventory_blob = bucket.blob("reference/inventory/initial.jsonl")
    inventory_jsonl = "\n".join([json.dumps(i) for i in INVENTORY])
    inventory_blob.upload_from_string(inventory_jsonl, content_type="application/jsonl")
    print(f"Subido: gs://{bucket_name}/reference/inventory/initial.jsonl")
    
    # Load Products to BQ
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    products_uri = f"gs://{bucket_name}/reference/products/catalog.jsonl"
    table_ref = f"{project_id}.{dataset_id}.products_catalog"
    load_job = bq_client.load_table_from_uri(products_uri, table_ref, job_config=job_config)
    load_job.result()
    print(f"Tabla {table_ref} cargada con {len(PRODUCTS)} registros.")

    # Load Inventory to BQ
    inv_uri = f"gs://{bucket_name}/reference/inventory/initial.jsonl"
    inv_table_ref = f"{project_id}.{dataset_id}.inventory_initial"
    load_job2 = bq_client.load_table_from_uri(inv_uri, inv_table_ref, job_config=job_config)
    load_job2.result()
    print(f"Tabla {inv_table_ref} cargada con {len(INVENTORY)} registros.")
    
    # Crear la tabla de movimientos (vacía si no existe) para registrar las variaciones
    schema_movements = [
        bigquery.SchemaField("movement_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("sku", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("quantity", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("movement_type", "STRING", mode="REQUIRED"), # RESERVATION, SALE, RESTORE
        bigquery.SchemaField("order_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    mov_table_ref = f"{project_id}.{dataset_id}.inventory_movements"
    try:
        bq_client.get_table(mov_table_ref)
        print(f"Tabla {mov_table_ref} ya existe.")
    except Exception:
        table = bigquery.Table(mov_table_ref, schema=schema_movements)
        table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="created_at")
        bq_client.create_table(table)
        print(f"Tabla {mov_table_ref} creada.")
        
    # Crear la tabla de snapshots (vacía si no existe) para registrar el inventario final de un run_id
    schema_snapshots = [
        bigquery.SchemaField("snapshot_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("sku", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("initial_stock", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("available_stock", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("reserved_stock", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("sold_stock", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("rejected_stock", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    snap_table_ref = f"{project_id}.{dataset_id}.inventory_snapshots"
    try:
        bq_client.get_table(snap_table_ref)
        print(f"Tabla {snap_table_ref} ya existe.")
    except Exception:
        table = bigquery.Table(snap_table_ref, schema=schema_snapshots)
        table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="created_at")
        bq_client.create_table(table)
        print(f"Tabla {snap_table_ref} creada.")

if __name__ == "__main__":
    generate_catalog()
    upload_to_gcs_and_bq()

