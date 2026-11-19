import unittest
from fastapi.testclient import TestClient
from backend.app.main import app

class TestStorePerformance(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_store_performance_endpoint(self):
        res = self.client.get("/api/store/performance")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        first = data[0]
        self.assertIn("store_id", first)
        self.assertIn("store_name", first)
        self.assertIn("location", first)
        self.assertIn("order_month", first)
        self.assertIn("currency_code", first)
        self.assertIn("total_orders", first)
        self.assertIn("completed_orders", first)
        self.assertIn("gross_sales", first)
        self.assertIn("net_sales", first)
        self.assertIn("total_returns", first)
        
        # Validar la regla de negocio de BQ para UCI: devoluciones aplicadas
        uci_rows = [r for r in data if r["store_id"] == "uci" and r["total_returns"] > 0]
        if uci_rows:
            sample = uci_rows[0]
            self.assertTrue(sample["net_sales"] < sample["gross_sales"], "Net sales debe ser menor que gross sales en meses con devoluciones (UCI).")

if __name__ == "__main__":
    unittest.main()
