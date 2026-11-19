"""
==============================================================================
LUMINA RETAIL - SUITE DE PRUEBAS UNITARIAS: SALVAGUARDAS DE INVENTARIO
==============================================================================
NOTA METODOLÓGICA:
Esta suite ejecuta pruebas unitarias deterministas en memoria sobre datos simulados,
validando la lógica exacta de los filtros defensivos de SQL (álgebra tri-valuada 3VL).
No interactúa con BigQuery ni emite consultas en la nube.
==============================================================================
"""

import unittest
from datetime import datetime, timezone
import pandas as pd
import numpy as np


def apply_streaming_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replica la semántica exacta del filtro SQL defensivo:
    WHERE (region IS NULL OR region != 'CYBER_TEST')
      AND (event_type IS NULL OR event_type != 'SYNTHETIC_CYBERDAY_STRESS')
    """
    if df.empty:
        return df.copy()

    cond_region = df["region"].isna() | (df["region"] != "CYBER_TEST")
    cond_type = df["event_type"].isna() | (df["event_type"] != "SYNTHETIC_CYBERDAY_STRESS")
    return df[cond_region & cond_type].copy()


def compute_stock_actual_simulated(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replica la lógica de stock_actual_vw:
    Filtrado previo -> ROW_NUMBER() OVER (PARTITION BY product_id, region ORDER BY event_timestamp DESC)
    """
    filtered = apply_streaming_filters(df)
    if filtered.empty:
        return pd.DataFrame(columns=[
            "product_id", "region", "stock_registrado", "fecha_ultimo_evento", "rn"
        ])

    filtered = filtered.sort_values("event_timestamp", ascending=False)
    filtered["rn"] = filtered.groupby(["product_id", "region"], dropna=False).cumcount() + 1
    actual = filtered[filtered["rn"] == 1].copy()
    actual["stock_registrado"] = actual["stock"]
    actual["fecha_ultimo_evento"] = actual["event_timestamp"]
    return actual[["product_id", "region", "stock_registrado", "fecha_ultimo_evento", "rn"]]


def compute_stock_risks_simulated(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replica la lógica de stock_risk_by_product_region:
    Filtrado previo -> GROUP BY product_id, region con métricas agregadas
    """
    filtered = apply_streaming_filters(df)
    if filtered.empty:
        return pd.DataFrame(columns=[
            "product_id", "region", "total_eventos", "stock_promedio",
            "stock_minimo", "stock_maximo", "alertas_criticas"
        ])

    agg = filtered.groupby(["product_id", "region"], dropna=False).agg(
        total_eventos=("stock", "count"),
        stock_promedio=("stock", "mean"),
        stock_minimo=("stock", "min"),
        stock_maximo=("stock", "max"),
        alertas_criticas=("stock", lambda s: int((s < 10).sum()))
    ).reset_index()
    agg["stock_promedio"] = agg["stock_promedio"].round(2)
    return agg


class TestInventorySafeguards(unittest.TestCase):
    def test_cp01_synthetic_event_cyber_test(self):
        """CP-01: Evento sintético explícito con region CYBER_TEST debe ser excluido."""
        data = [{
            "event_id": "SYNTH_01",
            "product_id": "CYBER_PROD_001",
            "region": "CYBER_TEST",
            "stock": 100,
            "event_type": "SYNTHETIC_CYBERDAY_STRESS",
            "event_timestamp": "2026-11-18T10:00:00Z"
        }]
        df = pd.DataFrame(data)
        filtered = apply_streaming_filters(df)
        self.assertTrue(filtered.empty)
        actual = compute_stock_actual_simulated(df)
        self.assertTrue(actual.empty)
        risks = compute_stock_risks_simulated(df)
        self.assertTrue(risks.empty)

    def test_cp02_synthetic_event_real_region(self):
        """CP-02: Evento sintético con región real (Lima) debe ser excluido por su event_type."""
        data = [{
            "event_id": "SYNTH_02",
            "product_id": "P001",
            "region": "Lima",
            "stock": 999,
            "event_type": "SYNTHETIC_CYBERDAY_STRESS",
            "event_timestamp": "2026-11-18T10:05:00Z"
        }]
        df = pd.DataFrame(data)
        filtered = apply_streaming_filters(df)
        self.assertTrue(filtered.empty)
        actual = compute_stock_actual_simulated(df)
        self.assertTrue(actual.empty)
        risks = compute_stock_risks_simulated(df)
        self.assertTrue(risks.empty)

    def test_cp03_operational_event_null_region(self):
        """CP-03: Evento operativo legítimo con region NULL debe ser estrictamente preservado."""
        data = [{
            "event_id": "OP_01",
            "product_id": "P002",
            "region": None,
            "stock": 42,
            "event_type": "STOCK_UPDATE",
            "event_timestamp": "2026-11-18T10:00:00Z"
        }]
        df = pd.DataFrame(data)
        filtered = apply_streaming_filters(df)
        self.assertEqual(len(filtered), 1)
        actual = compute_stock_actual_simulated(df)
        self.assertEqual(len(actual), 1)
        self.assertIsNone(actual.iloc[0]["region"])
        self.assertEqual(actual.iloc[0]["stock_registrado"], 42)

    def test_cp04_operational_event_null_event_type(self):
        """CP-04: Evento operativo legítimo con event_type NULL debe ser estrictamente preservado."""
        data = [{
            "event_id": "OP_02",
            "product_id": "P003",
            "region": "Norte",
            "stock": 18,
            "event_type": None,
            "event_timestamp": "2026-11-18T10:00:00Z"
        }]
        df = pd.DataFrame(data)
        filtered = apply_streaming_filters(df)
        self.assertEqual(len(filtered), 1)
        actual = compute_stock_actual_simulated(df)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual.iloc[0]["region"], "Norte")
        self.assertEqual(actual.iloc[0]["stock_registrado"], 18)

    def test_cp05_conflict_same_product_and_region(self):
        """
        CP-05: Conflicto entre evento operativo legítimo (10:00, stock=50) y evento sintético
        posterior (10:05, stock=999) para el mismo producto y región.
        El evento sintético no debe usurpar rn=1 ni distorsionar las métricas de riesgo.
        """
        data = [
            {
                "event_id": "OP_VALID",
                "product_id": "P001",
                "region": "Lima",
                "stock": 50,
                "event_type": "STOCK_UPDATE",
                "event_timestamp": "2026-11-18T10:00:00Z"
            },
            {
                "event_id": "SYNTH_INVALID",
                "product_id": "P001",
                "region": "Lima",
                "stock": 999,
                "event_type": "SYNTHETIC_CYBERDAY_STRESS",
                "event_timestamp": "2026-11-18T10:05:00Z"
            }
        ]
        df = pd.DataFrame(data)

        # 1. Comprobar stock_actual_vw
        actual = compute_stock_actual_simulated(df)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual.iloc[0]["product_id"], "P001")
        self.assertEqual(actual.iloc[0]["region"], "Lima")
        # El stock debe ser 50 (el operativo legítimo), no 999
        self.assertEqual(actual.iloc[0]["stock_registrado"], 50)

        # 2. Comprobar stock_risk_by_product_region
        risks = compute_stock_risks_simulated(df)
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks.iloc[0]["total_eventos"], 1)
        self.assertEqual(risks.iloc[0]["stock_promedio"], 50.0)
        self.assertEqual(risks.iloc[0]["stock_maximo"], 50)
        self.assertEqual(risks.iloc[0]["alertas_criticas"], 0)

    def test_cp06_empty_dataset(self):
        """CP-06: Cuando no existen registros, las funciones deben retornar DataFrames vacíos sin excepciones."""
        empty_df = pd.DataFrame(columns=[
            "event_id", "product_id", "region", "stock", "event_type", "event_timestamp"
        ])
        filtered = apply_streaming_filters(empty_df)
        self.assertTrue(filtered.empty)
        actual = compute_stock_actual_simulated(empty_df)
        self.assertTrue(actual.empty)
        risks = compute_stock_risks_simulated(empty_df)
        self.assertTrue(risks.empty)


if __name__ == "__main__":
    unittest.main()
