import unittest
import numpy as np
import pandas as pd
from scripts.evaluar_modelos_avanzados import build_features, compute_metrics, run_block_bootstrap


class TestMLAdvanced(unittest.TestCase):
    def setUp(self):
        # Crear panel sintético de 2 categorías x 20 semanas
        weeks = pd.date_range("2020-01-01", periods=20, freq="W-MON")
        categories = ["Cat_A", "Cat_B"]
        idx = pd.MultiIndex.from_product([categories, weeks], names=["categoria", "semana"])
        np.random.seed(42)
        values = np.random.randint(10, 100, size=len(idx))
        self.panel = pd.DataFrame(values, index=idx, columns=["lineas_articulo"]).reset_index()

    def test_no_data_leakage_in_features(self):
        df, feat_cols = build_features(self.panel, include_lag_26=False, one_hot_category=False, min_lag=1)

        cat_a = df[df["categoria"] == "Cat_A"].sort_values("semana").reset_index(drop=True)

        # Para cualquier semana t > 4, rolling_mean_4 debe depender de t-1, t-2, t-3, t-4, no de t
        for t in range(5, len(cat_a)):
            expected_mean = cat_a.loc[t-4:t-1, "lineas_articulo"].mean()
            actual_feature = cat_a.loc[t, "rolling_mean_4"]
            self.assertAlmostEqual(actual_feature, expected_mean, places=4)

            # lag_1 debe ser exactamente el valor en t-1
            expected_lag1 = cat_a.loc[t-1, "lineas_articulo"]
            self.assertEqual(cat_a.loc[t, "lag_1"], expected_lag1)

    def test_multistep_features_min_lag(self):
        # Para horizonte h=2 semanas, ningún feature debe contener información de t o t-1
        df_h2, feat_cols_h2 = build_features(self.panel, include_lag_26=False, one_hot_category=False, min_lag=2)
        self.assertNotIn("lag_1", feat_cols_h2)
        self.assertIn("lag_2", feat_cols_h2)

        cat_a = df_h2[df_h2["categoria"] == "Cat_A"].sort_values("semana").reset_index(drop=True)
        for t in range(6, len(cat_a)):
            # rolling_mean_4 con min_lag=2 debe promediar t-5, t-4, t-3, t-2
            expected_mean_h2 = cat_a.loc[t-5:t-2, "lineas_articulo"].mean()
            self.assertAlmostEqual(cat_a.loc[t, "rolling_mean_4"], expected_mean_h2, places=4)

    def test_log1p_expm1_inversion(self):
        y = np.array([0, 1, 5, 25, 100, 1500], dtype=float)
        y_trans = np.log1p(y)
        y_recovered = np.expm1(y_trans)
        np.testing.assert_allclose(y, y_recovered, rtol=1e-5)

    def test_compute_metrics_accuracy(self):
        actual = np.array([10.0, 20.0, 30.0])
        pred = np.array([12.0, 18.0, 35.0])

        mae, rmse, wape = compute_metrics(actual, pred)
        self.assertAlmostEqual(mae, 3.0, places=4)
        self.assertAlmostEqual(rmse, np.sqrt(11), places=4)
        self.assertAlmostEqual(wape, 15.0, places=4)

    def test_block_bootstrap_functionality(self):
        # Crear un dataframe sintético de test con 4 semanas y 2 categorías
        weeks = pd.date_range("2020-01-01", periods=4, freq="W-MON")
        cats = ["A", "B"]
        idx = pd.MultiIndex.from_product([cats, weeks], names=["categoria", "semana"])
        df_mock = pd.DataFrame(index=idx).reset_index()
        df_mock["lineas_articulo"] = [10, 15, 20, 25, 12, 14, 18, 22]
        df_mock["pred_lgb"] = [11, 14, 19, 24, 11, 15, 17, 21]
        df_mock["pred_naive"] = [12, 13, 18, 23, 10, 16, 16, 20]

        res = run_block_bootstrap(df_mock, n_boot=100, random_state=42)
        self.assertIn("diff_mean", res)
        self.assertIn("ci_95", res)
        self.assertIn("p_value_empirical", res)
        self.assertLessEqual(res["ci_95"][0], res["ci_95"][1])


if __name__ == "__main__":
    unittest.main()
