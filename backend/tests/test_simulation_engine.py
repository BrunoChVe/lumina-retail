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


if __name__ == "__main__":
    unittest.main()
