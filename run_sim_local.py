import sys
import os
import json
import time

sys.path.insert(0, 'backend')
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "127.0.0.1:19092"
os.environ["GOOGLE_CLOUD_PROJECT"] = "lumina-retail-001"

from app.simulation_engine import create_simulation_run, get_run_status

res = create_simulation_run({
    "name": "Prueba Controlada 20 Pedidos Local",
    "mode": "REAL_STREAMING",
    "scenario": "ORDER_CYCLE",
    "num_orders": 20,
    "num_products": 5,
    "initial_stock": 60,
    "simulate_idempotency": False,
    "authorized": True
})

print("INICIO SIMULACION:", res)
run_id = res.get("run_id")

if run_id:
    print(f"Haciendo polling al estado de {run_id}...")
    for _ in range(25):
        time.sleep(3)
        status_data = get_run_status(run_id)
        if not status_data:
            print("Status not found")
            continue
            
        pct = status_data.get('progress_pct', 0)
        state = status_data.get('status')
        print(f"Estado: {state} | Progreso: {pct}% | Procesados: {status_data.get('events_processed', 0)}")
        if state in ['COMPLETED', 'FAILED']:
            print("\nRESULTADO FINAL:")
            print(json.dumps(status_data, indent=2))
            break
