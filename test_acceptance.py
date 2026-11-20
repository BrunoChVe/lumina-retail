import sys
import os
import json
import time

# Forzar configuración local hacia Kafka por el túnel
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "127.0.0.1:19092"
os.environ["GOOGLE_CLOUD_PROJECT"] = "lumina-retail-001"
sys.path.insert(0, 'backend')

from app.simulation_engine import create_simulation_run, get_run_status, get_runs_history

res = create_simulation_run({
    "name": "Prueba de Aceptación 20 Pedidos",
    "mode": "REAL_STREAMING",
    "scenario": "ORDER_CYCLE",
    "num_orders": 20,
    "num_products": 5,
    "initial_stock": 60,
    "simulate_idempotency": False,
    "authorized": True
})

run_id = res.get("run_id")
print(f"RUN_ID: {run_id}")

for _ in range(20):
    time.sleep(3)
    status_data = get_run_status(run_id)
    if not status_data: continue
    state = status_data.get('status')
    pct = status_data.get('progress_pct', 0)
    print(f"Estado: {state} | Progreso: {pct}% | Procesados: {status_data.get('events_processed', 0)}")
    if state in ['COMPLETED', 'FAILED']:
        print("\n=== METRICAS DEL RUN ===")
        print(json.dumps(status_data, indent=2))
        break

print("\n=== HISTORIAL ===")
hist = get_runs_history()
for h in hist:
    print(f"Historial Run ID: {h['run_id']} | Nombre: {h['name']} | Estado: {h['status']}")

