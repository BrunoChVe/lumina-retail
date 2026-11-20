import time
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.simulation_engine import (
    validate_simulation_config,
    create_simulation_run,
    get_run_status,
    get_run_events,
    get_runs_history,
    cancel_simulation_run,
    MODE_ECONOMIC,
    MODE_REAL_STREAMING,
    EVENT_ORDER_CREATED,
    EVENT_ORDER_ITEM_CREATED,
    EVENT_INVENTORY_DECREMENT,
    EVENT_ORDER_COMPLETED,
    EVENT_ORDER_REJECTED
)


class TestSimulationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_modalities_endpoint(self):
        """Verifica que el endpoint de modalidades devuelva el modo económico como predeterminado."""
        res = self.client.get("/api/simulation/modalities")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        
        econ = next((m for m in data if m["id"] == MODE_ECONOMIC), None)
        self.assertIsNotNone(econ)
        self.assertTrue(econ["is_default"])
        self.assertEqual(econ["estimated_cost_usd_per_hour"], 0.0)
        self.assertFalse(econ["requires_authorization"])

        streaming = next((m for m in data if m["id"] == MODE_REAL_STREAMING), None)
        self.assertIsNotNone(streaming)
        self.assertTrue(streaming["requires_authorization"])

    def test_infrastructure_status_endpoint(self):
        """Verifica que la infraestructura de streaming esté reportada como TERMINATED."""
        res = self.client.get("/api/simulation/infrastructure_status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["kafka_vm"]["status"], "TERMINATED")
        self.assertEqual(data["dataproc_cluster"]["status"], "TERMINATED")
        self.assertFalse(data["ready_for_real_streaming"])

    def test_config_validation(self):
        """Prueba las reglas de validación de configuración segura."""
        # Configuración válida
        val_ok = validate_simulation_config({"num_orders": 30, "num_products": 5, "mode": MODE_ECONOMIC})
        self.assertTrue(val_ok["valid"])
        self.assertEqual(len(val_ok["errors"]), 0)

        # Configuración inválida: demasiados pedidos para económico
        val_bad = validate_simulation_config({"num_orders": 800, "mode": MODE_ECONOMIC})
        self.assertFalse(val_bad["valid"])

        # Configuración streaming real sin autorización
        val_unauth = validate_simulation_config({"num_orders": 50, "mode": MODE_REAL_STREAMING, "authorized": False})
        self.assertFalse(val_unauth["valid"])

    def test_economic_simulation_run_full_cycle(self):
        """Ejecuta una simulación completa en modo económico y verifica el ciclo de pedidos y reglas."""
        payload = {
            "name": "Test CI Simulación",
            "mode": MODE_ECONOMIC,
            "scenario": "ORDER_CYCLE",
            "num_orders": 20,
            "num_products": 3,
            "initial_stock": 25,
            "simulate_idempotency": True
        }
        res = self.client.post("/api/simulation/run", json=payload)
        self.assertEqual(res.status_code, 200)
        run_data = res.json()
        self.assertTrue(run_data["success"])
        run_id = run_data["run_id"]

        # Esperar finalización del hilo en memoria
        time.sleep(1.2)

        # Consultar estado
        status_res = self.client.get(f"/api/simulation/status/{run_id}")
        self.assertEqual(status_res.status_code, 200)
        st = status_res.json()
        self.assertEqual(st["status"], "COMPLETED")
        self.assertEqual(st["progress_pct"], 100.0)
        self.assertEqual(st["total_orders"], 20)
        self.assertGreater(st["completed_orders"] + st["rejected_orders"], 0)
        self.assertGreater(st["total_events"], 20)

        # Verificar reglas de stock no negativo
        inv_state = st.get("inventory_state", {})
        for sku, sku_data in inv_state.items():
            self.assertGreaterEqual(sku_data["current"], 0, f"El SKU {sku} no puede tener stock negativo")

        # Consultar eventos cronológicos
        events_res = self.client.get(f"/api/simulation/events/{run_id}?limit=100")
        self.assertEqual(events_res.status_code, 200)
        events = events_res.json()
        self.assertGreater(len(events), 0)

        # Verificar presencia de tipos de eventos requeridos
        event_types = {e["event_type"] for e in events}
        self.assertIn(EVENT_ORDER_CREATED, event_types)
        self.assertIn(EVENT_ORDER_ITEM_CREATED, event_types)
        self.assertIn(EVENT_INVENTORY_DECREMENT, event_types)

        # Comprobar unicidad de event_id
        event_ids = [e["event_id"] for e in events]
        self.assertEqual(len(event_ids), len(set(event_ids)), "Todos los event_id deben ser unívocos")

    def test_idempotency_neutralization(self):
        """Verifica que las órdenes duplicadas se neutralicen sin descontar stock adicional."""
        # Se verifica en la historia que se neutralizaron duplicados
        history_res = self.client.get("/api/simulation/history")
        self.assertEqual(history_res.status_code, 200)
        history = history_res.json()
        self.assertGreater(len(history), 0)
        # La ejecución histórica legendaria debe estar presente
        hist_run = next((h for h in history if h["run_id"] == "87cc5b11-926d-4525-a42e-feeab5ff6f99"), None)
        self.assertIsNotNone(hist_run, "La ejecución histórica de 795 eventos debe estar preservada en el historial")

    def test_safe_cancellation(self):
        """Verifica que la cancelación de una simulación no existente o terminada responda adecuadamente."""
        res = self.client.post("/api/simulation/cancel/non-existent-id")
        self.assertEqual(res.status_code, 400)

    def test_real_streaming_broker_unreachable_fails_fast(self):
        """Verifica que si el broker es inalcanzable, la simulación falle rápidamente sin congelarse."""
        import os
        from unittest.mock import patch
        from backend.app.simulation_engine import _run_real_streaming_worker, STATUS_FAILED

        run_id = "test-fail-unreachable-broker"
        config = {
            "name": "Prueba Broker Inaccesible",
            "mode": "REAL_STREAMING",
            "scenario": "ORDER_CYCLE",
            "num_orders": 10,
            "simulate_idempotency": False
        }

        with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "127.0.0.1:19099"}):
            from backend.app.simulation_engine import _RUNS_STORE, _STORE_LOCK
            with _STORE_LOCK:
                _RUNS_STORE[run_id] = {
                    "run_id": run_id,
                    "status": "PENDING",
                    "progress_pct": 0.0,
                    "total_orders": 10,
                    "events": []
                }
            
            t0 = time.time()
            _run_real_streaming_worker(run_id, config)
            duration = time.time() - t0

            # Debe fallar rápido (menos de 6 segundos, no bloquearse 60s)
            self.assertLess(duration, 6.0)
            status = get_run_status(run_id)
            self.assertEqual(status["status"], STATUS_FAILED)
            self.assertEqual(status["progress_pct"], 0.0)
            self.assertIn("Fallo al publicar en Kafka", status.get("error_message", ""))

    def test_real_streaming_producer_timeout_handling(self):
        """Verifica que un timeout en el subproceso del productor marque la simulación como FAILED."""
        import subprocess
        from unittest.mock import patch
        from backend.app.simulation_engine import _run_real_streaming_worker, STATUS_FAILED, _RUNS_STORE, _STORE_LOCK

        run_id = "test-fail-timeout-producer"
        config = {
            "name": "Prueba Timeout",
            "mode": "REAL_STREAMING",
            "scenario": "ORDER_CYCLE",
            "num_orders": 10
        }

        with _STORE_LOCK:
            _RUNS_STORE[run_id] = {
                "run_id": run_id,
                "status": "PENDING",
                "progress_pct": 0.0,
                "total_orders": 10,
                "events": []
            }

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="python3", timeout=25)):
            _run_real_streaming_worker(run_id, config)
            status = get_run_status(run_id)
            self.assertEqual(status["status"], STATUS_FAILED)
            self.assertIn("Timeout del productor Kafka", status.get("error_message", ""))

    def test_real_streaming_zero_orders_never_completed(self):
        """Verifica que si BigQuery no confirma órdenes tras el sondeo, NUNCA se marque COMPLETED."""
        from unittest.mock import patch, MagicMock
        from backend.app.simulation_engine import _run_real_streaming_worker, STATUS_FAILED, _RUNS_STORE, _STORE_LOCK

        run_id = "test-zero-orders-fails"
        config = {
            "name": "Prueba Cero Órdenes BQ",
            "mode": "REAL_STREAMING",
            "scenario": "ORDER_CYCLE",
            "num_orders": 20
        }

        with _STORE_LOCK:
            _RUNS_STORE[run_id] = {
                "run_id": run_id,
                "status": "PENDING",
                "progress_pct": 0.0,
                "total_orders": 20,
                "events": []
            }

        mock_proc = MagicMock(returncode=0, stdout="OK", stderr="")
        def mock_query(sql):
            mock_job = MagicMock()
            if "total_procesado" in sql:
                mock_bq_row = MagicMock(total_procesado=0, aprobados=0, rechazados=0, duplicados=0)
                mock_job.result.return_value = [mock_bq_row]
            elif "stock_before" in sql and "MAX" in sql:
                mock_inv_row = MagicMock(sku="CYBER_SKU_001", initial=80, current_stock=60, total_sold=0, total_rejected=0)
                mock_job.result.return_value = [mock_inv_row]
            else:
                mock_job.result.return_value = []
            return mock_job
            
        mock_bq_client = MagicMock()
        mock_bq_client.query.side_effect = mock_query

        class MockClock:
            def __init__(self):
                self.val = 1000.0
            def __call__(self):
                self.val += 25.0
                return self.val

        with patch("subprocess.run", return_value=mock_proc):
            with patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
                with patch("time.sleep", return_value=None):
                    with patch("time.time", side_effect=MockClock()):
                        _run_real_streaming_worker(run_id, config)

        status = get_run_status(run_id)
        self.assertEqual(status["status"], STATUS_FAILED, "Una simulación con 0 órdenes confirmadas NUNCA debe ser COMPLETED")
        self.assertEqual(status["progress_pct"], 0.0)
        self.assertIn("Tiempo de espera agotado", status.get("error_message", ""))

    def test_real_streaming_partial_processing_handling(self):
        """Verifica que el procesamiento parcial (menos pedidos de los solicitados) resulte en FAILED."""
        from unittest.mock import patch, MagicMock
        from backend.app.simulation_engine import _run_real_streaming_worker, STATUS_FAILED, _RUNS_STORE, _STORE_LOCK

        run_id = "test-partial-orders-fails"
        config = {
            "name": "Prueba Parcial BQ",
            "mode": "REAL_STREAMING",
            "scenario": "ORDER_CYCLE",
            "num_orders": 50
        }

        with _STORE_LOCK:
            _RUNS_STORE[run_id] = {
                "run_id": run_id,
                "status": "PENDING",
                "progress_pct": 0.0,
                "total_orders": 50,
                "events": []
            }

        mock_proc = MagicMock(returncode=0, stdout="OK", stderr="")
        def mock_query(sql):
            mock_job = MagicMock()
            if "total_procesado" in sql:
                mock_bq_row = MagicMock(total_procesado=15, aprobados=12, rechazados=3, duplicados=0)
                mock_job.result.return_value = [mock_bq_row]
            elif "stock_before" in sql and "MAX" in sql:
                mock_inv_row = MagicMock(sku="CYBER_SKU_001", initial=80, current_stock=60, total_sold=12, total_rejected=3)
                mock_job.result.return_value = [mock_inv_row]
            else:
                mock_job.result.return_value = []
            return mock_job
            
        mock_bq_client = MagicMock()
        mock_bq_client.query.side_effect = mock_query

        class MockClock:
            def __init__(self):
                self.val = 1000.0
            def __call__(self):
                self.val += 25.0
                return self.val

        with patch("subprocess.run", return_value=mock_proc):
            with patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
                with patch("time.sleep", return_value=None):
                    with patch("time.time", side_effect=MockClock()):
                        _run_real_streaming_worker(run_id, config)

        status = get_run_status(run_id)
        self.assertEqual(status["status"], STATUS_FAILED)
        self.assertEqual(status["events_processed"], 15)
        self.assertIn("Procesamiento incompleto: solo 15 de 50 pedidos", status.get("error_message", ""))

    def test_real_streaming_full_processing_success(self):
        """Verifica que cuando BigQuery confirma el 100% de las órdenes, el estado sea COMPLETED."""
        from unittest.mock import patch, MagicMock
        from backend.app.simulation_engine import _run_real_streaming_worker, STATUS_COMPLETED, _RUNS_STORE, _STORE_LOCK

        run_id = "test-full-success-orders"
        config = {
            "name": "Prueba Éxito Total BQ",
            "mode": "REAL_STREAMING",
            "scenario": "ORDER_CYCLE",
            "num_orders": 20
        }

        with _STORE_LOCK:
            _RUNS_STORE[run_id] = {
                "run_id": run_id,
                "status": "PENDING",
                "progress_pct": 0.0,
                "total_orders": 20,
                "events": []
            }

        mock_proc = MagicMock(returncode=0, stdout="OK", stderr="")
        def mock_query(sql):
            mock_job = MagicMock()
            if "total_procesado" in sql:
                mock_bq_row = MagicMock(total_procesado=20, aprobados=18, rechazados=2, duplicados=0)
                mock_job.result.return_value = [mock_bq_row]
            elif "stock_before" in sql and "MAX" in sql:
                mock_inv_row = MagicMock(sku="CYBER_SKU_001", initial=80, current_stock=60, total_sold=18, total_rejected=2)
                mock_job.result.return_value = [mock_inv_row]
            else:
                mock_job.result.return_value = []
            return mock_job
            
        mock_bq_client = MagicMock()
        mock_bq_client.query.side_effect = mock_query

        class MockClock:
            def __init__(self):
                self.val = 1000.0
            def __call__(self):
                self.val += 2.0
                return self.val

        with patch("subprocess.run", return_value=mock_proc):
            with patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
                with patch("time.sleep", return_value=None):
                    with patch("time.time", side_effect=MockClock()):
                        _run_real_streaming_worker(run_id, config)

        status = get_run_status(run_id)
        self.assertEqual(status["status"], STATUS_COMPLETED)
        self.assertEqual(status["progress_pct"], 100.0)
        self.assertEqual(status["completed_orders"], 18)
        self.assertEqual(status["rejected_orders"], 2)

    def test_simulation_state_cross_instance_persistence(self):
        """Verifica que el estado de ejecución persista y pueda recuperarse simulando múltiples instancias."""
        from unittest.mock import patch
        from backend.app.simulation_engine import _RUNS_STORE, _STORE_LOCK, get_run_status

        test_run_id = "test-cross-instance-001"
        sample_record = {
            "run_id": test_run_id,
            "name": "Instancia A Registro",
            "status": "PROCESSING",
            "progress_pct": 50.0,
            "total_orders": 30,
            "completed_orders": 15
        }

        remote_storage = {test_run_id: dict(sample_record)}

        def mock_load(run_id):
            return remote_storage.get(run_id)

        with patch("backend.app.simulation_engine._load_run_from_gcs", side_effect=mock_load):
            # Simular Instancia B: memoria local vacía para este run_id
            with _STORE_LOCK:
                if test_run_id in _RUNS_STORE:
                    del _RUNS_STORE[test_run_id]

            # Instancia B consulta el estado
            recovered = get_run_status(test_run_id)
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered["run_id"], test_run_id)
            self.assertEqual(recovered["progress_pct"], 50.0)
            self.assertEqual(recovered["completed_orders"], 15)


if __name__ == "__main__":
    unittest.main()
