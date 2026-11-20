import subprocess
import json
import time
import urllib.request
import urllib.error

# 1. Obtener IAP token
token_cmd = ['gcloud', 'auth', 'print-identity-token', '--audiences=192488032202-4mophflrcg9fq62pnsucor6qt319g7ih.apps.googleusercontent.com']
token = subprocess.check_output(token_cmd).decode().strip()

# 2. Iniciar simulación
url_run = "https://lumina-retail-sv5avv2ypq-uc.a.run.app/api/simulation/run"
payload = json.dumps({
    "name": "Prueba Controlada 20 Pedidos",
    "mode": "REAL_STREAMING",
    "scenario": "ORDER_CYCLE",
    "num_orders": 20,
    "num_products": 5,
    "initial_stock": 60,
    "simulate_idempotency": False,
    "authorized": True
}).encode('utf-8')

req = urllib.request.Request(url_run, data=payload, headers={
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode())
        print("INICIO SIMULACION:", res_data)
        run_id = res_data.get("run_id")
except urllib.error.HTTPError as e:
    print("ERROR AL INICIAR:", e.code, e.read().decode())
    exit(1)

# 3. Polling de estado
if run_id:
    url_status = f"https://lumina-retail-sv5avv2ypq-uc.a.run.app/api/simulation/status/{run_id}"
    req_status = urllib.request.Request(url_status, headers={
        'Authorization': f'Bearer {token}'
    })
    
    print(f"Haciendo polling al estado de {run_id}...")
    for _ in range(25):
        time.sleep(3)
        try:
            with urllib.request.urlopen(req_status) as response:
                status_data = json.loads(response.read().decode())
                pct = status_data.get('progress_pct', 0)
                state = status_data.get('status')
                print(f"Estado: {state} | Progreso: {pct}% | Procesados: {status_data.get('events_processed', 0)}")
                if state in ['COMPLETED', 'FAILED']:
                    print("\nRESULTADO FINAL:")
                    print(json.dumps(status_data, indent=2))
                    break
        except urllib.error.HTTPError as e:
            print("ERROR AL CONSULTAR ESTADO:", e.code, e.read().decode())
