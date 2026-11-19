import unittest
from fastapi.testclient import TestClient
from backend.app.main import app


class TestLuminaRetailAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("project", data)
        self.assertIn("dataset", data)
        self.assertIn("streaming_dataset", data)
        self.assertTrue(data.get("frontend_mounted"))

    def test_commercial_summary(self):
        res = self.client.get("/api/commercial/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)
        sources = {row["source_system"]: row for row in data}
        self.assertIn("olist", sources)
        self.assertIn("thelook", sources)
        self.assertEqual(sources["olist"]["currency_code"], "BRL")
        self.assertEqual(sources["thelook"]["currency_code"], "USD")
        for row in data:
            self.assertIn("total_orders", row)
            self.assertIn("total_product_sales", row)
            self.assertIn("completed_orders", row)

    def test_commercial_monthly(self):
        res = self.client.get("/api/commercial/monthly")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        first = data[0]
        self.assertIn("order_month", first)
        self.assertIn("source_system", first)
        self.assertIn("total_product_sales", first)

    def test_commercial_categories(self):
        res = self.client.get("/api/commercial/categories")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for row in data:
            self.assertLessEqual(row["category_rank"], 15)
            self.assertIn("category", row)
            self.assertIn("total_sales", row)

    def test_commercial_products(self):
        res = self.client.get("/api/commercial/products")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for row in data:
            self.assertLessEqual(row["sales_rank"], 20)
            self.assertIn("source_product_id", row)
            self.assertIn("total_sales", row)

    def test_logistics_summary(self):
        res = self.client.get("/api/logistics/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)
        sources = {row["source_system"]: row for row in data}
        self.assertIn("olist", sources)
        self.assertIn("thelook", sources)
        self.assertEqual(sources["olist"]["late_delivery_data_status"], "available")
        self.assertEqual(sources["thelook"]["late_delivery_data_status"], "not_available")
        for row in data:
            self.assertIn("total_orders", row)
            self.assertIn("valid_shipments", row)
            self.assertIn("valid_deliveries", row)

    def test_logistics_monthly(self):
        res = self.client.get("/api/logistics/monthly")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        first = data[0]
        self.assertIn("order_cohort_month", first)
        self.assertIn("source_system", first)

    def test_inventory_current(self):
        res = self.client.get("/api/inventory/current")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for row in data:
            self.assertIn("product_id", row)
            self.assertIn("region", row)
            self.assertIn("stock_registrado", row)
            self.assertIn(row["estado_stock"], ["CRITICO", "BAJO", "NORMAL"])
            self.assertIn(row["estado_frescura"], ["ACTUALIZADO", "DESACTUALIZADO", "SIN_FECHA"])

    def test_inventory_risks(self):
        res = self.client.get("/api/inventory/risks")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for row in data:
            self.assertIn("product_id", row)
            self.assertIn("region", row)
            self.assertIn("total_eventos", row)
            self.assertIn("alertas_criticas", row)
            self.assertIn("porcentaje_alertas", row)

    def test_predictive_metrics(self):
        res = self.client.get("/api/predictive/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        metrics = {row["metric"]: row["value"] for row in data}
        self.assertIn("MAE", metrics)
        self.assertIn("RMSE", metrics)
        self.assertIn("WAPE", metrics)
        self.assertGreater(metrics["MAE"], 0)
        self.assertGreater(metrics["RMSE"], 0)
        self.assertGreater(metrics["WAPE"], 0)

    def test_predictive_predictions(self):
        res = self.client.get("/api/predictive/predictions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        first = data[0]
        self.assertIn("semana", first)
        self.assertIn("categoria", first)
        self.assertIn("actual", first)
        self.assertIn("prediccion", first)
        self.assertIn("error_absoluto", first)


if __name__ == "__main__":
    unittest.main()
