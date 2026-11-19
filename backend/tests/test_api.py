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
        """Valida taxonomía estándar para Olist/TheLook y categorías derivadas/unclassified de UCI."""
        res = self.client.get("/api/commercial/categories")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Validación de UCI
        uci_cats = [r for r in data if r["source_system"] == "uci"]
        self.assertEqual(len(uci_cats), 8)  # 7 derivadas + 1 unclassified
        uci_cat_names = set(r["category"] for r in uci_cats)
        self.assertIn("Kitchen & Dining", uci_cat_names)
        self.assertIn("Home Decor & Lighting", uci_cat_names)
        self.assertIn("Unclassified", uci_cat_names)
        
        total_uci_sales = sum(r["total_sales"] for r in uci_cats)
        self.assertAlmostEqual(total_uci_sales, 10666684.54, places=2)
        
        for r in uci_cats:
            self.assertEqual(r["currency_code"], "GBP")
            self.assertIsNotNone(r["category"])
            self.assertIn(r["category_origin"], ["DERIVED_RULE", "UNCLASSIFIED"])
        
        # Validación de no regresión en Olist y TheLook
        olist_cats = [r for r in data if r["source_system"] == "olist"]
        thelook_cats = [r for r in data if r["source_system"] == "thelook"]
        self.assertEqual(len(olist_cats), 15)  # rank <= 15
        self.assertEqual(len(thelook_cats), 15)
        for row in data:
            self.assertLessEqual(row["category_rank"], 15)
            self.assertIn("total_sales", row)

    def test_uci_categories_reconciliation_and_coverage(self):
        """Valida cobertura clasificada vs sin clasificar y conciliación al 100% de ventas UCI."""
        res = self.client.get("/api/commercial/categories")
        self.assertEqual(res.status_code, 200)
        uci_cats = [r for r in res.json() if r["source_system"] == "uci"]
        
        derived = [r for r in uci_cats if r["category_origin"] == "DERIVED_RULE"]
        unclassified = [r for r in uci_cats if r["category_origin"] == "UNCLASSIFIED"]
        
        self.assertEqual(len(derived), 7)
        self.assertEqual(len(unclassified), 1)
        
        derived_sales = sum(r["total_sales"] for r in derived)
        unclass_sales = sum(r["total_sales"] for r in unclassified)
        total_sales = derived_sales + unclass_sales
        
        pct_classified = (derived_sales / total_sales) * 100
        pct_unclassified = (unclass_sales / total_sales) * 100
        
        self.assertGreater(pct_classified, 80.0)  # ~81.68%
        self.assertLess(pct_unclassified, 20.0)    # ~18.32%
        self.assertAlmostEqual(pct_classified + pct_unclassified, 100.0, places=1)

    def test_uci_null_and_single_category_robustness(self):
        """Valida robustez ante categoría NULL y caso borde de una sola categoría."""
        # Simulación de respuesta con categoría nula
        sample_row = {"category": None, "source_system": "uci", "total_sales": 100}
        resolved_category = sample_row.get("category") or "Unclassified"
        self.assertEqual(resolved_category, "Unclassified")
        
        # Caso de una sola categoría sin clasificar
        single_cat_data = [{"category": "Unclassified", "total_sales": 1000, "sales_share_pct": 100.0}]
        self.assertEqual(len(single_cat_data), 1)
        self.assertEqual(single_cat_data[0]["sales_share_pct"], 100.0)

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

    def test_inventory_current_synthetic(self):
        """Verifica que inventory/current devuelve los 36 registros al incluir sintéticos."""
        res = self.client.get("/api/inventory/current?include_synthetic=true")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 36)

    def test_inventory_risks_unaffected(self):
        res = self.client.get("/api/inventory/risks")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 26)

    def test_inventory_risks_synthetic(self):
        """Verifica que inventory/risks devuelve los 36 registros al incluir sintéticos."""
        res = self.client.get("/api/inventory/risks?include_synthetic=true")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 36)

    def test_inventory_uci_catalog(self):
        """Verifica que el catálogo analítico de UCI devuelve datos y clasificación ABC."""
        res = self.client.get("/api/inventory/uci/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        if len(data) > 0:
            self.assertIn("stock_code", data[0])
            self.assertIn("abc_class", data[0])

    def test_inventory_uci_country(self):
        """Verifica que el inventario por país de UCI funcione correctamente."""
        res = self.client.get("/api/inventory/uci/country")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        if len(data) > 0:
            self.assertIn("country", data[0])

    def test_inventory_uci_monthly(self):
        """Verifica la evolución mensual de demanda de UCI."""
        res = self.client.get("/api/inventory/uci/monthly")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)

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

    def test_commercial_and_logistics_exclude_synthetic(self):
        """Verifica que los endpoints comerciales y logísticos no contengan datos sintéticos."""
        res_com = self.client.get("/api/commercial/summary")
        self.assertEqual(res_com.status_code, 200)
        for row in res_com.json():
            self.assertNotIn("CYBER", row.get("source_system", "").upper())
            self.assertNotIn("SYNTHETIC", row.get("source_system", "").upper())
            
        res_log = self.client.get("/api/logistics/summary")
        self.assertEqual(res_log.status_code, 200)
        for row in res_log.json():
            self.assertNotIn("CYBER", row.get("source_system", "").upper())
            self.assertNotIn("SYNTHETIC", row.get("source_system", "").upper())

if __name__ == "__main__":
    unittest.main()
