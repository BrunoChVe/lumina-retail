#!/usr/bin/env python3
"""
Cliente de prueba para validación de autenticación perimetral IAP
LUMINA Retail — Cloud Run Endpoint Test Client

Genera un ID Token OIDC firmado utilizando la audiencia del OAuth Client ID de IAP:
  192488032202-4mophflrcg9fq62pnsucor6qt319g7ih.apps.googleusercontent.com
Y consulta los endpoints protegidos sin exponer ni registrar el token en logs.
"""

import argparse
import subprocess
import sys
import urllib.request
import urllib.error

IAP_CLIENT_ID = "192488032202-4mophflrcg9fq62pnsucor6qt319g7ih.apps.googleusercontent.com"
CLOUD_RUN_URL = "https://lumina-retail-192488032202.us-central1.run.app"


def get_iap_bearer_token(client_id: str) -> str:
    """Obtiene un token de identidad OIDC con la audiencia correcta de IAP impersonando la SA."""
    sa = "lumina-iap-validator@lumina-retail-001.iam.gserviceaccount.com"
    cmd = [
        "gcloud", "auth", "print-identity-token", 
        f"--audiences={client_id}",
        f"--impersonate-service-account={sa}",
        "--include-email"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error generando token OIDC: {res.stderr.strip()}")
    # gcloud impersonation often prints warnings to stderr. stdout has the token.
    token = res.stdout.strip().split('\n')[-1]
    return token


def test_endpoint(endpoint_path: str = "/api/simulation/modalities", client_id: str = IAP_CLIENT_ID):
    """Prueba la invocación contra Cloud Run protegido por IAP."""
    target_url = f"{CLOUD_RUN_URL}{endpoint_path}"
    print(f"[IAP Client] Objetivo: {target_url}")
    print(f"[IAP Client] Audiencia: {client_id}")

    try:
        token = get_iap_bearer_token(client_id)
    except Exception as e:
        print(f"[ERROR] No se pudo obtener el token OIDC: {e}")
        sys.exit(1)

    req = urllib.request.Request(target_url)
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            print(f"[IAP Client] Respuesta HTTP {status_code} OK")
            print(f"[IAP Client] Body (primeros 200 caracteres): {body[:200]}...")
            return True
    except urllib.error.HTTPError as he:
        print(f"[IAP Client] Error HTTP {he.code}: {he.reason}")
        err_body = he.read().decode("utf-8", errors="replace")
        print(f"[IAP Client] Detalle: {err_body[:300]}")
        return False
    except Exception as ex:
        print(f"[IAP Client] Excepción de conexión: {ex}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente de validación IAP LUMINA Retail")
    parser.add_argument("--endpoint", default="/api/simulation/modalities", help="Ruta de la API a probar")
    parser.add_argument("--client-id", default=IAP_CLIENT_ID, help="OAuth Client ID de IAP")
    args = parser.parse_args()

    success = test_endpoint(args.endpoint, args.client_id)
    sys.exit(0 if success else 1)
