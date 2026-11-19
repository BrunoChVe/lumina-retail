import unittest
from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
PARQUET_FILE = BASE_DIR / "data" / "silver" / "uci_online_retail" / "uci_sales_silver.parquet"


class TestUCIOnlineRetailProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PARQUET_FILE.exists():
            raise FileNotFoundError(f"Archivo Parquet no encontrado: {PARQUET_FILE}")
        cls.df = pd.read_parquet(PARQUET_FILE)

    def test_row_count(self):
        self.assertEqual(len(self.df), 541909)

    def test_unique_source_item_id(self):
        self.assertTrue(self.df["source_item_id"].is_unique)
        self.assertEqual(self.df["source_item_id"].nunique(), len(self.df))

    def test_currency_isolation(self):
        currencies = self.df["currency_code"].unique()
        self.assertEqual(list(currencies), ["GBP"])

    def test_source_system(self):
        systems = self.df["source_system"].unique()
        self.assertEqual(list(systems), ["uci"])

    def test_gross_and_return_signs(self):
        self.assertTrue((self.df["gross_sales_gbp"] >= 0).all())
        self.assertTrue((self.df["return_sales_gbp"] <= 0).all())

    def test_net_sales_equation(self):
        expected_net = self.df["gross_sales_gbp"] + self.df["return_sales_gbp"]
        diff = np.abs(self.df["net_sales_gbp"] - expected_net)
        self.assertTrue((diff < 1e-4).all())

    def test_financial_totals(self):
        gross = self.df["gross_sales_gbp"].sum()
        returns = self.df["return_sales_gbp"].sum()
        net = self.df["net_sales_gbp"].sum()

        self.assertAlmostEqual(gross, 10666684.54, places=1)
        self.assertAlmostEqual(returns, -896812.49, places=1)
        self.assertAlmostEqual(net, 9769872.05, places=1)

    def test_temporal_bounds(self):
        min_date = self.df["order_created_at"].min()
        max_date = self.df["order_created_at"].max()
        self.assertEqual(min_date.year, 2010)
        self.assertEqual(min_date.month, 12)
        self.assertEqual(max_date.year, 2011)
        self.assertEqual(max_date.month, 12)


if __name__ == "__main__":
    unittest.main()
