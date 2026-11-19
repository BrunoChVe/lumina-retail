import unittest
from unittest.mock import patch, MagicMock
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
        """Valida que commercial/summary incluya Olist (BRL), TheLook (USD) y UCI (GBP) de forma aislada."""
        res = self.client.get("/api/commercial/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)  # Olist, TheLook, UCI
        sources = {row["source_system"]: row for row in data}
        self.assertIn("olist", sources)
        self.assertIn("thelook", sources)
        self.assertIn("uci", sources)
        
        # Aislamiento monetario estricto
        self.assertEqual(sources["olist"]["currency_code"], "BRL")
        self.assertEqual(sources["thelook"]["currency_code"], "USD")
        self.assertEqual(sources["uci"]["currency_code"], "GBP")
        self.assertEqual(sources["uci"]["currency_status"], "documented")
        
        for row in data:
            self.assertIn("total_orders", row)
            self.assertIn("total_product_sales", row)
            self.assertIn("completed_orders", row)
            self.assertGreater(row["total_orders"], 0)
            self.assertGreater(row["total_product_sales"], 0)

    def test_commercial_monthly(self):
        """Valida granularidad mensual por fuente."""
        res = self.client.get("/api/commercial/monthly")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 132)  # Olist(24) + TheLook(95) + UCI(13)
        sources = set(r["source_system"] for r in data)
        self.assertEqual(sources, {"olist", "thelook", "uci"})
        first = data[0]
        self.assertIn("order_month", first)
        self.assertIn("source_system", first)
        self.assertIn("currency_code", first)
        self.assertIn("total_product_sales", first)

    def test_commercial_categories(self):
        """Valida taxonomía estándar y manejo de categorías nulas de UCI."""
        res = self.client.get("/api/commercial/categories")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        uci_cats = [r for r in data if r["source_system"] == "uci"]
        self.assertEqual(len(uci_cats), 1)
        self.assertIsNone(uci_cats[0]["category"])
        self.assertEqual(uci_cats[0]["category_rank"], 1)
        self.assertEqual(uci_cats[0]["currency_code"], "GBP")
        
        for row in data:
            self.assertLessEqual(row["category_rank"], 15)
            self.assertIn("total_sales", row)

    def test_commercial_products(self):
        """Valida top productos por fuente."""
        res = self.client.get("/api/commercial/products")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 60)  # 20 Olist + 20 TheLook + 20 UCI
        sources = set(r["source_system"] for r in data)
        self.assertEqual(sources, {"olist", "thelook", "uci"})
        for row in data:
            self.assertLessEqual(row["sales_rank"], 20)
            self.assertIn("source_product_id", row)
            self.assertIn("total_sales", row)
            self.assertIn("currency_code", row)

    def test_logistics_summary(self):
        """Valida que Logistics conserve tardanza no disponible para TheLook."""
        res = self.client.get("/api/logistics/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)  # Olist y TheLook (UCI excluida)
        sources = {row["source_system"]: row for row in data}
        self.assertIn("olist", sources)
        self.assertIn("thelook", sources)
        self.assertNotIn("uci", sources)
        self.assertEqual(sources["olist"]["late_delivery_data_status"], "available")
        self.assertEqual(sources["thelook"]["late_delivery_data_status"], "not_available")
        self.assertIsNone(sources["thelook"]["late_delivery_rate_pct"])
        self.assertIsNotNone(sources["olist"]["late_delivery_rate_pct"])
        for row in data:
            self.assertIn("total_orders", row)
            self.assertIn("valid_shipments", row)
            self.assertIn("valid_deliveries", row)

    def test_logistics_monthly(self):
        res = self.client.get("/api/logistics/monthly")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 120)  # 25 Olist + 95 TheLook
        sources = set(r["source_system"] for r in data)
        self.assertEqual(sources, {"olist", "thelook"})
        first = data[0]
        self.assertIn("order_cohort_month", first)
        self.assertIn("source_system", first)

    def test_inventory_current_unaffected(self):
        """Verifica que inventory/current no fue afectado y mantiene los 26 registros."""
        res = self.client.get("/api/inventory/current")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 26)

    def test_inventory_risks_unaffected(self):
        res = self.client.get("/api/inventory/risks")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 26)

    def test_predictive_metrics_unaffected(self):
        """Valida las 3 métricas de evaluación del modelo LightGBM en Gold WAP."""
        res = self.client.get("/api/predictive/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)
        metrics = {r["metric"]: r["value"] for r in data}
        self.assertIn("MAE", metrics)
        self.assertIn("RMSE", metrics)
        self.assertIn("WAPE", metrics)
        self.assertGreater(metrics["MAE"], 0)
        self.assertGreater(metrics["RMSE"], 0)
        self.assertGreater(metrics["WAPE"], 0)
        for row in data:
            self.assertEqual(row["model_name"], "LightGBM")
            self.assertEqual(row["n_test_rows"], 888)

    def test_predictive_predictions_unaffected(self):
        """Valida las 888 predicciones semanales por categoría en Gold WAP."""
        res = self.client.get("/api/predictive/predictions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 888)
        first = data[0]
        self.assertIn("semana", first)
        self.assertIn("categoria", first)
        self.assertIn("actual", first)
        self.assertIn("prediccion", first)
        self.assertIn("error_absoluto", first)
        self.assertGreaterEqual(first["prediccion"], 0)

    @patch("backend.app.main.client.query")
    def test_unreleased_domain_controlled_error(self, mock_query):
        """Valida que ante ausencia de publicación se devuelva HTTP 503 controlado en commercial."""
        mock_empty_job = MagicMock()
        mock_empty_job.result.return_value = []
        
        mock_chk_job = MagicMock()
        mock_chk_job.result.return_value = [{"current_run_id": None, "status": "EMPTY"}]
        
        mock_query.side_effect = [mock_empty_job, mock_chk_job]
        
        res = self.client.get("/api/commercial/summary")
        self.assertEqual(res.status_code, 503)
        self.assertIn("No existe una versión publicada válida", res.json()["detail"])

    @patch("backend.app.main.client.query")
    def test_unreleased_predictive_controlled_error(self, mock_query):
        """Valida que ante ausencia de publicación se devuelva HTTP 503 controlado en predictive."""
        mock_empty_job = MagicMock()
        mock_empty_job.result.return_value = []
        
        mock_chk_job = MagicMock()
        mock_chk_job.result.return_value = [{"current_run_id": None, "status": "EMPTY"}]
        
        mock_query.side_effect = [mock_empty_job, mock_chk_job]
        
        res = self.client.get("/api/predictive/metrics")
        self.assertEqual(res.status_code, 503)
        self.assertIn("No existe una versión publicada válida para el dominio 'predictive'", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
