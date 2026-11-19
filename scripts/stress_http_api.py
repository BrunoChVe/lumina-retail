import argparse
import asyncio
import logging
import time
from typing import List, Tuple
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("stress_http_api")

BIGQUERY_ENDPOINTS = [
    "/api/inventory/current",
    "/api/inventory/risks",
    "/api/commercial/summary",
    "/api/commercial/monthly",
    "/api/commercial/categories",
    "/api/commercial/products",
    "/api/logistics/summary",
    "/api/logistics/monthly",
    "/api/predictive/metrics",
    "/api/predictive/predictions"
]


async def worker(
    session: aiohttp.ClientSession,
    base_url: str,
    endpoint: str,
    stop_event: asyncio.Event,
    results: list
):
    url = f"{base_url.rstrip('/')}{endpoint}"
    timeout_cfg = aiohttp.ClientTimeout(total=5.0, connect=2.0)

    while not stop_event.is_set():
        t0 = time.perf_counter()
        try:
            async with session.get(url, timeout=timeout_cfg) as resp:
                await resp.read()
                latency = (time.perf_counter() - t0) * 1000
                results.append((resp.status, latency))
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - t0) * 1000
            results.append((504, latency))
        except Exception:
            latency = (time.perf_counter() - t0) * 1000
            results.append((500, latency))

        await asyncio.sleep(0.02)


async def run_http_stage(base_url: str, endpoint: str, concurrency: int, duration_sec: int, dry_run: bool = False):
    logger.info(f"--- Iniciando Escenario HTTP: {concurrency} clientes concurrentes en {endpoint} por {duration_sec}s ---")
    if dry_run:
        logger.info("[Dry Run] Simulación local de 50 peticiones exitosas (sin emitir a la red)...")
        return True, 50, 0, 50.0, [10.0] * 50

    results: List[Tuple[int, float]] = []
    stop_event = asyncio.Event()

    conn = aiohttp.TCPConnector(limit=concurrency + 10, keepalive_timeout=30)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [
            asyncio.create_task(worker(session, base_url, endpoint, stop_event, results))
            for _ in range(concurrency)
        ]

        start_time = time.perf_counter()
        # Monitoreo en vivo cada 5 segundos
        while time.perf_counter() - start_time < duration_sec:
            await asyncio.sleep(5)
            if results:
                recent = results[-100:]
                errs = sum(1 for status, _ in recent if status >= 500)
                err_rate = (errs / len(recent)) * 100
                if err_rate > 5.0:
                    logger.critical(f"CIRCUIT BREAKER: Tasa de error 5xx en vivo ({err_rate:.1f}%) supera el 5%. Abortando escenario.")
                    stop_event.set()
                    break

        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await session.close()
        await conn.close()

    total_reqs = len(results)
    if total_reqs == 0:
        logger.warning("No se completaron peticiones.")
        return False, 0, 0, 0.0, []

    errors_5xx = sum(1 for s, _ in results if s >= 500)
    latencies = sorted([lat for _, lat in results])
    p50 = latencies[int(total_reqs * 0.50)]
    p95 = latencies[int(total_reqs * 0.95)]
    p99 = latencies[int(total_reqs * 0.99)]
    rps = total_reqs / duration_sec

    logger.info(
        f"Fin de escenario: {total_reqs} reqs | Errores 5xx: {errors_5xx} ({errors_5xx/total_reqs*100:.1f}%) | "
        f"RPS: {rps:.1f} | Latencias -> p50: {p50:.1f}ms, p95: {p95:.1f}ms, p99: {p99:.1f}ms"
    )
    return errors_5xx / total_reqs <= 0.05, total_reqs, errors_5xx, rps, latencies


def main():
    parser = argparse.ArgumentParser(description="Prueba de estrés HTTP progresiva para Cloud Run (CyberDay)")
    parser.add_argument("--url", default="https://lumina-retail-192488032202.us-central1.run.app", help="URL base del servicio")
    parser.add_argument("--endpoint", default="/api/health", help="Endpoint a estresar (por defecto /api/health)")
    parser.add_argument("--stages", default="5,10,25,50", help="Concurrencia de usuarios (1x, 2x, 5x, 10x)")
    parser.add_argument("--duration", type=int, default=60, help="Duración en segundos por escenario")
    parser.add_argument("--allow-analytical-endpoints", action="store_true", help="Permitir estresar endpoints dependientes de BigQuery")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación local")
    args = parser.parse_args()

    if args.endpoint in BIGQUERY_ENDPOINTS and not args.allow_analytical_endpoints and not args.dry_run:
        logger.error(
            f"PROTECCIÓN ACTIVADA: El endpoint '{args.endpoint}' ejecuta consultas en BigQuery. "
            "Estresarlo a alta concurrencia superará las cuotas de consultas concurrentes y generará costos innecesarios. "
            "Utilice '/api/health' para estresar Cloud Run, o pase '--allow-analytical-endpoints' conscientemente."
        )
        return

    stages = [int(x.strip()) for x in args.stages.split(",")]
    logger.info(f"Destino de prueba HTTP: {args.url}{args.endpoint}")
    logger.info(f"Escenarios de concurrencia: {stages}")
    logger.info(f"Modo Dry Run: {args.dry_run}")

    for concurrency in stages:
        success, reqs, errs, rps, _ = asyncio.run(
            run_http_stage(args.url, args.endpoint, concurrency, args.duration, dry_run=args.dry_run)
        )
        if not success:
            logger.warning("Prueba HTTP detenida anticipadamente por superación de umbrales de fallo.")
            break
        time.sleep(3)  # Cooldown entre escenarios


if __name__ == "__main__":
    main()
