#!/usr/bin/env python3
"""
LUMINA RETAIL — SCRIPT DE RECUPERACIÓN Y RECONSTRUCCIÓN DE INVENTARIO HISTÓRICO
==============================================================================
Componente: Herramienta de Recuperación Operativa
Funcionalidad:
  1. Identifica ejecuciones de Streaming Real registradas en BigQuery (orders_stream_events)
     que carecen de persistencia estructurada en Google Cloud Storage.
  2. Ejecuta la consulta SQL de agregación atómica de inventario (MAX(stock_before),
     MIN(stock_after), unidades vendidas y pedidos rechazados) por cada SKU.
  3. Reconstruye el documento JSON canónico de la ejecución con su run_id original
     y lo almacena en gs://lumina-retail-001-data/simulation_runs/{run_id}.json.
  4. Garantiza idempotencia y no altera eventos históricos ni tablas analíticas.
==============================================================================
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.simulation_engine import _save_run_to_gcs, _list_runs_from_gcs
from google.cloud import bigquery


def recover_historical_runs():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001")
    runs_in_gcs = {r.get("run_id") for r in _list_runs_from_gcs() if r.get("run_id")}
    client = bigquery.Client(project=project_id)
    
    print(f"[Recovery] Consultando ejecuciones existentes en BigQuery dataset lumina_streaming...")
    query = "SELECT DISTINCT run_id FROM `lumina-retail-001.lumina_streaming.orders_stream_events` WHERE run_id IS NOT NULL"
    res = list(client.query(query).result())
    
    recovered_count = 0
    for row in res:
        run_id = row.run_id
        if run_id not in runs_in_gcs:
            print(f"[Recovery] Reconstruyendo run_id: {run_id}")
            sql_summary = f"""
            SELECT min(processed_at) as start_t, max(processed_at) as end_t, count(*) as total_events
            FROM `lumina-retail-001.lumina_streaming.orders_stream_events` WHERE run_id = '{run_id}'
            """
            summary = list(client.query(sql_summary).result())[0]
            
            sql_inv = f"""
            SELECT product_id as sku, MAX(stock_before) as initial, MIN(stock_after) as current_stock,
                   SUM(CASE WHEN order_status = 'APPROVED' THEN quantity ELSE 0 END) as total_sold,
                   COUNTIF(order_status = 'REJECTED') as total_rejected
            FROM `lumina-retail-001.lumina_streaming.orders_stream_events`
            WHERE run_id = '{run_id}' AND product_id IS NOT NULL
            GROUP BY product_id
            """
            inv_res = list(client.query(sql_inv).result())
            inv = {}
            for r in inv_res:
                inv[r.sku] = {
                    "initial": r.initial,
                    "current": r.current_stock,
                    "total_sold": r.total_sold,
                    "total_rejected": r.total_rejected,
                    "low_alert": r.current_stock <= 20
                }
            
            start_iso = summary.start_t.isoformat() if summary.start_t else None
            end_iso = summary.end_t.isoformat() if summary.end_t else None
            duration = round((summary.end_t - summary.start_t).total_seconds(), 2) if (summary.end_t and summary.start_t) else 0.0

            run_record = {
                "run_id": run_id,
                "name": "Ejecución Recuperada (Streaming Real)",
                "mode": "REAL_STREAMING",
                "scenario": "RECOVERED",
                "status": "COMPLETED",
                "progress_pct": 100.0,
                "created_at": start_iso,
                "start_time": start_iso,
                "end_time": end_iso,
                "duration_sec": duration,
                "total_orders": summary.total_events,
                "total_events": summary.total_events,
                "inventory_state": inv
            }
            if _save_run_to_gcs(run_id, run_record):
                print(f"[Recovery] Exitosamente persistido en GCS: {run_id}")
                recovered_count += 1
            else:
                print(f"[WARN] No se pudo persistir en GCS: {run_id}")
                
    print(f"[Recovery] Proceso finalizado. Total ejecuciones recuperadas: {recovered_count}")


if __name__ == "__main__":
    recover_historical_runs()
