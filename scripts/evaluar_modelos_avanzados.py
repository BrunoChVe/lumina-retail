import os
import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor
import lightgbm as lgb

warnings.filterwarnings("ignore")

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "lumina-retail-001")
DATASET = os.getenv("BQ_DATASET", "lumina_stage")
SOURCE_TABLE = f"{PROJECT}.{DATASET}.gold_demand_olist_weekly"


def load_panel_data():
    client = bigquery.Client(project=PROJECT)
    query = (
        "SELECT semana, categoria, lineas_articulo "
        f"FROM `{SOURCE_TABLE}` "
        "WHERE fuente = 'olist' "
        "ORDER BY semana, categoria"
    )
    df = client.query(query).to_dataframe()
    df["semana"] = pd.to_datetime(df["semana"])
    df["lineas_articulo"] = df["lineas_articulo"].astype(int)

    weeks = pd.date_range(df["semana"].min(), df["semana"].max(), freq="W-MON")
    categories = sorted(df["categoria"].unique())
    full_index = pd.MultiIndex.from_product(
        [categories, weeks],
        names=["categoria", "semana"]
    )

    panel = (
        df.groupby(["categoria", "semana"])["lineas_articulo"]
          .sum()
          .reindex(full_index, fill_value=0)
          .reset_index()
          .sort_values(["categoria", "semana"])
          .reset_index(drop=True)
    )
    return panel, weeks, categories


def build_features(panel, include_lag_26=True, one_hot_category=False, min_lag=1):
    """
    Construye features temporales con retardo mínimo parametrizable (min_lag >= 1)
    para soportar evaluaciones multi-step sin fuga de datos.
    """
    df = panel.copy()
    grouped = df.groupby("categoria")["lineas_articulo"]

    lags = [l for l in [1, 2, 4, 8, 13] if l >= min_lag]
    if include_lag_26 and 26 >= min_lag:
        lags.append(26)

    for lag in lags:
        df[f"lag_{lag}"] = grouped.shift(lag)

    df["lag_52"] = grouped.shift(52)  # Para evaluación Seasonal Naive

    for window in [4, 8, 13]:
        df[f"rolling_mean_{window}"] = (
            df.groupby("categoria")["lineas_articulo"]
            .transform(lambda s: s.shift(min_lag).rolling(window).mean())
        )

    df["month"] = df["semana"].dt.month
    df["week_of_year"] = df["semana"].dt.isocalendar().week.astype(int)

    feature_cols = [f"lag_{lag}" for lag in lags] + [
        "rolling_mean_4", "rolling_mean_8", "rolling_mean_13",
        "month", "week_of_year"
    ]

    if one_hot_category:
        cat_dummies = pd.get_dummies(df["categoria"], prefix="cat", drop_first=True, dtype=int)
        dummy_cols = list(cat_dummies.columns)
        df = pd.concat([df, cat_dummies], axis=1)
        feature_cols.extend(dummy_cols)

    return df, feature_cols


def compute_metrics(actual, pred):
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    diff = actual - pred
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    wape = float(np.sum(np.abs(diff)) / np.sum(actual) * 100) if np.sum(actual) > 0 else float("nan")
    return mae, rmse, wape


def run_rolling_origin_cv(train_df, feature_cols, model_factory, use_log=False, n_splits=3, fold_weeks=6):
    """
    Validación temporal Rolling-Origin (Expanding Window) estrictamente dentro del conjunto de entrenamiento.
    """
    train_weeks = sorted(train_df["semana"].unique())
    cv_wapes = []

    for i in range(n_splits, 0, -1):
        cutoff_idx = len(train_weeks) - (i * fold_weeks)
        val_end_idx = cutoff_idx + fold_weeks

        train_cutoff_week = train_weeks[cutoff_idx]
        val_end_week = train_weeks[min(val_end_idx - 1, len(train_weeks) - 1)]

        f_train = train_df[train_df["semana"] < train_cutoff_week].dropna(subset=feature_cols)
        f_val = train_df[(train_df["semana"] >= train_cutoff_week) & (train_df["semana"] <= val_end_week)].dropna(subset=feature_cols)

        if len(f_train) == 0 or len(f_val) == 0:
            continue

        X_tr = f_train[feature_cols]
        y_tr = np.log1p(f_train["lineas_articulo"]) if use_log else f_train["lineas_articulo"]
        X_v = f_val[feature_cols]
        y_v_actual = f_val["lineas_articulo"].to_numpy()

        model = model_factory()
        model.fit(X_tr, y_tr)

        raw_pred = model.predict(X_v)
        pred = np.expm1(raw_pred) if use_log else raw_pred
        pred = np.maximum(pred, 0)

        _, _, fold_wape = compute_metrics(y_v_actual, pred)
        cv_wapes.append(fold_wape)

    return float(np.mean(cv_wapes)) if cv_wapes else float("nan")


def run_block_bootstrap(test_df, n_boot=1000, random_state=42):
    """
    Block Bootstrap por semana: remuestrea las semanas completas con reemplazo (conservando las 74 categorías juntas)
    para evaluar la estabilidad de la diferencia de WAPE entre LightGBM y Naive.
    """
    rng = np.random.default_rng(random_state)
    weeks = test_df["semana"].unique()
    diffs = []
    wape_lgb_list = []
    wape_nv_list = []

    for _ in range(n_boot):
        sample_weeks = rng.choice(weeks, size=len(weeks), replace=True)
        boot_parts = [test_df[test_df["semana"] == w] for w in sample_weeks]
        boot_sample = pd.concat(boot_parts, ignore_index=True)

        y_true = boot_sample["lineas_articulo"].to_numpy()
        pred_lgb = boot_sample["pred_lgb"].to_numpy()
        pred_nv = boot_sample["pred_naive"].to_numpy()

        _, _, w_lgb = compute_metrics(y_true, pred_lgb)
        _, _, w_nv = compute_metrics(y_true, pred_nv)

        wape_lgb_list.append(w_lgb)
        wape_nv_list.append(w_nv)
        diffs.append(w_lgb - w_nv)

    diffs = np.array(diffs)
    ci_lower = np.percentile(diffs, 2.5)
    ci_upper = np.percentile(diffs, 97.5)
    p_value = np.mean(diffs >= 0)  # Proporción donde LightGBM no supera a Naive

    return {
        "diff_mean": float(np.mean(diffs)),
        "ci_95": (float(ci_lower), float(ci_upper)),
        "p_value_empirical": float(p_value),
        "pct_lgb_wins": float(np.mean(diffs < 0) * 100)
    }


def run_multistep_evaluation(panel, weeks, horizons=[1, 2, 4]):
    """
    Evaluación multi-step para horizontes de 1, 2 y 4 semanas.
    Para horizonte h, el modelo y el Naive solo pueden utilizar información hasta t-h.
    """
    test_start = weeks[-12]
    test_end = weeks[-1]
    multistep_results = []

    for h in horizons:
        df_h, feats_h = build_features(panel, include_lag_26=False, one_hot_category=True, min_lag=h)

        train_data = df_h[df_h["semana"] < test_start].dropna(subset=feats_h).copy()
        test_data = df_h[(df_h["semana"] >= test_start) & (df_h["semana"] <= test_end)].copy()

        y_test_actual = test_data["lineas_articulo"].to_numpy()

        # Naive lag_h
        pred_naive_h = test_data[f"lag_{h}"].to_numpy()
        mae_nv, rmse_nv, wape_nv = compute_metrics(y_test_actual, pred_naive_h)

        # LightGBM (OHE + Log1p) configurado con horizonte h
        X_tr = train_data[feats_h]
        y_tr = np.log1p(train_data["lineas_articulo"])
        X_te = test_data[feats_h]

        model = lgb.LGBMRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
            random_state=42, verbose=-1, n_jobs=-1
        )
        model.fit(X_tr, y_tr)
        pred_lgb_h = np.maximum(np.expm1(model.predict(X_te)), 0)
        mae_lgb, rmse_lgb, wape_lgb = compute_metrics(y_test_actual, pred_lgb_h)

        multistep_results.append({
            "Horizonte (h)": f"t+{h} semanas",
            "WAPE Naive": f"{wape_nv:.2f}%",
            "WAPE LightGBM": f"{wape_lgb:.2f}%",
            "MAE Naive": f"{mae_nv:.2f}",
            "MAE LightGBM": f"{mae_lgb:.2f}",
            "Ventaja LightGBM": f"{wape_nv - wape_lgb:+.2f}%",
            "Ganador": "LightGBM" if wape_lgb < wape_nv else "Naive"
        })

    return pd.DataFrame(multistep_results)


def run_single_origin_4week_forecast(panel, weeks):
    """
    Pronóstico de 4 semanas consecutivas desde un único origen temporal t0 (weeks[-13]).
    No se permite el uso de ventas reales de semanas intermedias.
    Compara LightGBM (OHE + Log1p) y Naive bajo exactamente las mismas condiciones.
    """
    t0 = weeks[-13]
    test_weeks = [weeks[-12], weeks[-11], weeks[-10], weeks[-9]]
    actual_t0 = panel[panel["semana"] == t0].set_index("categoria")["lineas_articulo"]

    single_origin_results = []
    all_y_true = []
    all_pred_naive = []
    all_pred_lgb = []

    for h, target_week in enumerate(test_weeks, start=1):
        df_h, feats_h = build_features(panel, include_lag_26=False, one_hot_category=True, min_lag=h)
        train_data = df_h[df_h["semana"] <= t0].dropna(subset=feats_h)
        test_row = df_h[df_h["semana"] == target_week]

        y_true = test_row["lineas_articulo"].to_numpy()
        pred_nv = test_row["categoria"].map(actual_t0).to_numpy()

        X_tr = train_data[feats_h]
        y_tr = np.log1p(train_data["lineas_articulo"])
        X_te = test_row[feats_h]

        model = lgb.LGBMRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
            random_state=42, verbose=-1, n_jobs=-1
        )
        model.fit(X_tr, y_tr)
        pred_lgb = np.maximum(np.expm1(model.predict(X_te)), 0)

        mae_nv, rmse_nv, wape_nv = compute_metrics(y_true, pred_nv)
        mae_lgb, rmse_lgb, wape_lgb = compute_metrics(y_true, pred_lgb)

        single_origin_results.append({
            "Horizonte": f"t+{h} ({target_week.date()})",
            "WAPE Naive": f"{wape_nv:.2f}%",
            "WAPE LightGBM": f"{wape_lgb:.2f}%",
            "MAE Naive": f"{mae_nv:.2f}",
            "MAE LightGBM": f"{mae_lgb:.2f}",
            "RMSE Naive": f"{rmse_nv:.2f}",
            "RMSE LightGBM": f"{rmse_lgb:.2f}",
            "Ventaja LGB": f"{wape_nv - wape_lgb:+.2f}%",
            "Ganador": "LightGBM" if wape_lgb < wape_nv else "Naive"
        })

        all_y_true.extend(y_true)
        all_pred_naive.extend(pred_nv)
        all_pred_lgb.extend(pred_lgb)

    agg_mae_nv, agg_rmse_nv, agg_wape_nv = compute_metrics(all_y_true, all_pred_naive)
    agg_mae_lgb, agg_rmse_lgb, agg_wape_lgb = compute_metrics(all_y_true, all_pred_lgb)

    agg_summary = {
        "obs_total": len(all_y_true),
        "total_demand_actual": int(sum(all_y_true)),
        "total_demand_naive": float(sum(all_pred_naive)),
        "total_demand_lgb": float(sum(all_pred_lgb)),
        "wape_naive": agg_wape_nv,
        "wape_lgb": agg_wape_lgb,
        "mae_naive": agg_mae_nv,
        "mae_lgb": agg_mae_lgb,
        "rmse_naive": agg_rmse_nv,
        "rmse_lgb": agg_rmse_lgb,
        "wape_advantage": agg_wape_nv - agg_wape_lgb,
        "t0": t0.date()
    }

    return pd.DataFrame(single_origin_results), agg_summary


def evaluate_candidate_models():
    t_start = time.perf_counter()
    print("Cargando datos históricos y construyendo panel...")
    panel, weeks, categories = load_panel_data()

    test_start = weeks[-12]
    test_end = weeks[-1]
    print(f"Ventana de prueba final: {test_start.date()} a {test_end.date()} (12 semanas, 888 obs)")

    # 1. Configuración estándar (con lag_26)
    df_std, std_features = build_features(panel, include_lag_26=True, one_hot_category=False)
    # 2. Configuración sin lag_26 (gana 13 semanas adicionales de train)
    df_no26, no26_features = build_features(panel, include_lag_26=False, one_hot_category=False)
    # 3. Configuración con One-Hot Encoding
    df_ohe, ohe_features = build_features(panel, include_lag_26=False, one_hot_category=True)

    # Separar train y test (test siempre tiene las mismas 888 observaciones)
    test_mask = (panel["semana"] >= test_start) & (panel["semana"] <= test_end)
    y_test_actual = panel.loc[test_mask, "lineas_articulo"].to_numpy()

    assert len(y_test_actual) == 888, f"Error: test set tiene {len(y_test_actual)} filas en vez de 888"

    results = []

    # Baselines
    pred_naive = df_std.loc[test_mask, "lag_1"].to_numpy()
    mae_n, rmse_n, wape_n = compute_metrics(y_test_actual, pred_naive)
    results.append({
        "Modelo": "Naive Baseline (t-1)",
        "Familia": "Heurístico",
        "Configuración": "Persistencia semanal",
        "CV WAPE (Train)": "-",
        "MAE": mae_n,
        "RMSE": rmse_n,
        "WAPE": wape_n,
        "Observaciones": len(y_test_actual)
    })

    pred_snaive = df_std.loc[test_mask, "lag_52"].to_numpy()
    mae_sn, rmse_sn, wape_sn = compute_metrics(y_test_actual, pred_snaive)
    results.append({
        "Modelo": "Seasonal Naive (t-52)",
        "Familia": "Heurístico",
        "Configuración": "Estacional anual (52 semanas)",
        "CV WAPE (Train)": "-",
        "MAE": mae_sn,
        "RMSE": rmse_sn,
        "WAPE": wape_sn,
        "Observaciones": len(y_test_actual)
    })

    experiments = [
        {
            "name": "XGBoost (Original / Baseline)",
            "family": "XGBoost",
            "df": df_std,
            "features": std_features,
            "use_log": False,
            "desc": "Con lag_26, escala lineal",
            "factory": lambda: XGBRegressor(
                n_estimators=400, max_depth=4, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, tree_method="hist", objective="reg:squarederror", n_jobs=-1
            )
        },
        {
            "name": "XGBoost (Sin lag_26)",
            "family": "XGBoost",
            "df": df_no26,
            "features": no26_features,
            "use_log": False,
            "desc": "Sin lag_26 (+13 semanas train), escala lineal",
            "factory": lambda: XGBRegressor(
                n_estimators=400, max_depth=4, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, tree_method="hist", objective="reg:squarederror", n_jobs=-1
            )
        },
        {
            "name": "XGBoost (Log1p)",
            "family": "XGBoost",
            "df": df_no26,
            "features": no26_features,
            "use_log": True,
            "desc": "Sin lag_26, target transformado con log1p",
            "factory": lambda: XGBRegressor(
                n_estimators=300, max_depth=4, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, tree_method="hist", objective="reg:squarederror", n_jobs=-1
            )
        },
        {
            "name": "XGBoost (OHE Categoría + Log1p)",
            "family": "XGBoost",
            "df": df_ohe,
            "features": ohe_features,
            "use_log": True,
            "desc": "Sin lag_26, One-Hot Categoría + log1p",
            "factory": lambda: XGBRegressor(
                n_estimators=300, max_depth=5, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, tree_method="hist", objective="reg:squarederror", n_jobs=-1
            )
        },
        {
            "name": "LightGBM (Base)",
            "family": "LightGBM",
            "df": df_no26,
            "features": no26_features,
            "use_log": False,
            "desc": "Sin lag_26, escala lineal",
            "factory": lambda: lgb.LGBMRegressor(
                n_estimators=300, max_depth=5, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, verbose=-1, n_jobs=-1
            )
        },
        {
            "name": "LightGBM (Log1p)",
            "family": "LightGBM",
            "df": df_no26,
            "features": no26_features,
            "use_log": True,
            "desc": "Sin lag_26, target transformado con log1p",
            "factory": lambda: lgb.LGBMRegressor(
                n_estimators=300, max_depth=5, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, verbose=-1, n_jobs=-1
            )
        },
        {
            "name": "LightGBM (OHE Categoría + Log1p)",
            "family": "LightGBM",
            "df": df_ohe,
            "features": ohe_features,
            "use_log": True,
            "desc": "Sin lag_26, One-Hot Categoría + log1p",
            "factory": lambda: lgb.LGBMRegressor(
                n_estimators=350, max_depth=6, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8, reg_lambda=5,
                random_state=42, verbose=-1, n_jobs=-1
            )
        }
    ]

    saved_predictions = {"actual": y_test_actual, "naive": pred_naive}

    print("\nEjecutando validación Rolling-Origin en Train y evaluación en Test...")
    for exp in experiments:
        df_exp = exp["df"]
        feats = exp["features"]
        use_log = exp["use_log"]
        factory = exp["factory"]

        train_data = df_exp[df_exp["semana"] < test_start].dropna(subset=feats).copy()
        test_data = df_exp[(df_exp["semana"] >= test_start) & (df_exp["semana"] <= test_end)].copy()

        cv_wape = run_rolling_origin_cv(train_data, feats, factory, use_log=use_log, n_splits=3, fold_weeks=6)

        X_train = train_data[feats]
        y_train = np.log1p(train_data["lineas_articulo"]) if use_log else train_data["lineas_articulo"]

        model = factory()
        model.fit(X_train, y_train)

        X_test = test_data[feats]
        raw_pred = model.predict(X_test)
        pred = np.expm1(raw_pred) if use_log else raw_pred
        pred = np.maximum(pred, 0)

        mae, rmse, wape = compute_metrics(y_test_actual, pred)
        saved_predictions[exp["name"]] = pred

        results.append({
            "Modelo": exp["name"],
            "Familia": exp["family"],
            "Configuración": exp["desc"],
            "CV WAPE (Train)": f"{cv_wape:.2f}%" if not np.isnan(cv_wape) else "-",
            "MAE": mae,
            "RMSE": rmse,
            "WAPE": wape,
            "Observaciones": len(test_data)
        })
        print(f"-> {exp['name']}: WAPE Test = {wape:.2f}% | CV Train = {cv_wape:.2f}%")

    res_df = pd.DataFrame(results)

    # --- ANÁLISIS DE SENSIBILIDAD: SIN SEMANA TRUNCADA (11 semanas, 814 observaciones) ---
    print("\nCalculando análisis de sensibilidad excluyendo semana truncada (2018-08-27)...")
    test_eval_df = panel[test_mask][["semana", "categoria", "lineas_articulo"]].copy()
    test_eval_df["pred_lgb"] = saved_predictions["LightGBM (OHE Categoría + Log1p)"]
    test_eval_df["pred_xgb"] = saved_predictions["XGBoost (Original / Baseline)"]
    test_eval_df["pred_naive"] = pred_naive

    test_11_df = test_eval_df[test_eval_df["semana"] < test_end].copy()
    y_test_11 = test_11_df["lineas_articulo"].to_numpy()
    pred_nv_11 = test_11_df["pred_naive"].to_numpy()
    pred_lgb_11 = test_11_df["pred_lgb"].to_numpy()
    pred_xgb_11 = test_11_df["pred_xgb"].to_numpy()

    sens_results = [
        {"Modelo": "Naive Baseline (t-1)", "Obs": len(y_test_11), "WAPE (11 sem)": f"{compute_metrics(y_test_11, pred_nv_11)[2]:.2f}%", "MAE": f"{compute_metrics(y_test_11, pred_nv_11)[0]:.2f}", "RMSE": f"{compute_metrics(y_test_11, pred_nv_11)[1]:.2f}"},
        {"Modelo": "XGBoost (Original)", "Obs": len(y_test_11), "WAPE (11 sem)": f"{compute_metrics(y_test_11, pred_xgb_11)[2]:.2f}%", "MAE": f"{compute_metrics(y_test_11, pred_xgb_11)[0]:.2f}", "RMSE": f"{compute_metrics(y_test_11, pred_xgb_11)[1]:.2f}"},
        {"Modelo": "LightGBM (OHE + Log1p)", "Obs": len(y_test_11), "WAPE (11 sem)": f"{compute_metrics(y_test_11, pred_lgb_11)[2]:.2f}%", "MAE": f"{compute_metrics(y_test_11, pred_lgb_11)[0]:.2f}", "RMSE": f"{compute_metrics(y_test_11, pred_lgb_11)[1]:.2f}"}
    ]
    sens_df = pd.DataFrame(sens_results)

    # --- BLOCK BOOTSTRAP POR SEMANA (1,000 remuestreos) ---
    print("\nEjecutando Block Bootstrap por semana (B=1,000)...")
    boot_res = run_block_bootstrap(test_eval_df, n_boot=1000)

    # --- EVALUACIÓN MULTI-STEP (h = 1, 2, 4 semanas) ---
    print("\nEjecutando evaluación Multi-Step (h = 1, 2, 4 semanas)...")
    multistep_df = run_multistep_evaluation(panel, weeks, horizons=[1, 2, 4])

    # --- PRONÓSTICO 4 SEMANAS CONSECUTIVAS DESDE ORIGEN ÚNICO (296 obs) ---
    print("\nEjecutando pronóstico de 4 semanas consecutivas desde origen único (t0)...")
    single_origin_df, single_origin_agg = run_single_origin_4week_forecast(panel, weeks)

    elapsed = time.perf_counter() - t_start
    print(f"\nEvaluación completa ejecutada en {elapsed:.2f} segundos.")

    return res_df, sens_df, boot_res, multistep_df, single_origin_df, single_origin_agg


if __name__ == "__main__":
    res, sens, boot, multi, s_orig_df, s_orig_agg = evaluate_candidate_models()
    print("\n" + "=" * 95)
    print("1. EVALUACIÓN BASE OFICIAL (888 OBSERVACIONES EXACTAS)")
    print("=" * 95)
    print(res.to_string(index=False))

    print("\n" + "=" * 95)
    print("2. ANÁLISIS DE SENSIBILIDAD SIN SEMANA TRUNCADA 2018-08-27 (814 OBSERVACIONES)")
    print("=" * 95)
    print(sens.to_string(index=False))

    print("\n" + "=" * 95)
    print("3. BLOCK BOOTSTRAP POR SEMANA (LIGHTGBM vs. NAIVE - B=1000)")
    print("=" * 95)
    print(f"Diferencia media de WAPE (LGB - Naive): {boot['diff_mean']:.2f}%")
    print(f"Intervalo de confianza al 95%:          [{boot['ci_95'][0]:.2f}%, {boot['ci_95'][1]:.2f}%]")
    print(f"Porcentaje de muestras donde gana LGB:   {boot['pct_lgb_wins']:.1f}%")
    print(f"P-value empírico bootstrap (H0: LGB>=NV): {boot['p_value_empirical']:.4f}")

    print("\n" + "=" * 95)
    print("4. EVALUACIÓN MULTI-STEP (HORIZONTES h = 1, 2, 4 SEMANAS)")
    print("=" * 95)
    print(multi.to_string(index=False))

    print("\n" + "=" * 95)
    print(f"5. PRONÓSTICO DE 4 SEMANAS CONSECUTIVAS DESDE ORIGEN ÚNICO {s_orig_agg['t0']} (296 OBS)")
    print("=" * 95)
    print(s_orig_df.to_string(index=False))
    print("\n--- MÉTRICAS AGREGADAS DEL BLOQUE DE 4 SEMANAS (296 OBSERVACIONES) ---")
    print(f"Demanda Real Total:         {s_orig_agg['total_demand_actual']:,} líneas de artículo")
    print(f"Pronóstico Total Naive:     {s_orig_agg['total_demand_naive']:,.0f} líneas de artículo")
    print(f"Pronóstico Total LightGBM:  {s_orig_agg['total_demand_lgb']:,.0f} líneas de artículo")
    print(f"Naive     -> WAPE: {s_orig_agg['wape_naive']:.2f}% | MAE: {s_orig_agg['mae_naive']:.2f} | RMSE: {s_orig_agg['rmse_naive']:.2f}")
    print(f"LightGBM  -> WAPE: {s_orig_agg['wape_lgb']:.2f}% | MAE: {s_orig_agg['mae_lgb']:.2f} | RMSE: {s_orig_agg['rmse_lgb']:.2f}")
    print(f"Ventaja neta LightGBM:      {s_orig_agg['wape_advantage']:+.2f}% de reducción en WAPE")
