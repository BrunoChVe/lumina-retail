import json
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

PROJECT = "lumina-retail-001"
DATASET = "lumina_stage"

SOURCE = f"{PROJECT}.{DATASET}.gold_demand_olist_weekly"
METRICS_TABLE = f"{PROJECT}.{DATASET}.model_evaluation_metrics"
PREDICTIONS_TABLE = f"{PROJECT}.{DATASET}.model_evaluation_predictions"

RUN_ID = str(uuid.uuid4())
client = bigquery.Client(project=PROJECT)

# 1. Leer datos
query = f"""
SELECT semana, categoria, lineas_articulo
FROM `{SOURCE}`
WHERE fuente = 'olist'
ORDER BY semana, categoria
"""

df = client.query(query).to_dataframe()
df["semana"] = pd.to_datetime(df["semana"])
df["lineas_articulo"] = df["lineas_articulo"].astype(int)

# 2. Construir panel semanal completo por categoría
weeks = pd.date_range(
    df["semana"].min(),
    df["semana"].max(),
    freq="W-MON"
)
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

# 3. Ingeniería de variables: solo información pasada
grouped = panel.groupby("categoria")["lineas_articulo"]

for lag in [1, 2, 4, 8, 13, 26]:
    panel[f"lag_{lag}"] = grouped.shift(lag)

for window in [4, 8, 13]:
    panel[f"rolling_mean_{window}"] = (
        panel.groupby("categoria")["lineas_articulo"]
        .transform(lambda s: s.shift(1).rolling(window).mean())
    )

panel["month"] = panel["semana"].dt.month
panel["week_of_year"] = panel["semana"].dt.isocalendar().week.astype(int)

features = [
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_13", "lag_26",
    "rolling_mean_4", "rolling_mean_8", "rolling_mean_13",
    "month", "week_of_year"
]

panel = panel.dropna(subset=features).copy()

# 4. Separación temporal: últimas 12 semanas
test_start = weeks[-12]
test_end = weeks[-1]

train = panel[panel["semana"] < test_start].copy()
test = panel[
    (panel["semana"] >= test_start) &
    (panel["semana"] <= test_end)
].copy()

if train.empty or test.empty:
    raise ValueError("No hay suficientes registros para entrenar y evaluar.")

X_train = train[features]
y_train = train["lineas_articulo"]
X_test = test[features]
y_test = test["lineas_articulo"]

# 5. Entrenar XGBoost
params = {
    "n_estimators": 400,
    "max_depth": 4,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 5,
    "random_state": 42,
    "tree_method": "hist",
    "objective": "reg:squarederror",
    "n_jobs": -1
}

model = XGBRegressor(**params)
model.fit(X_train, y_train)

predictions = np.maximum(model.predict(X_test), 0)
actual = y_test.to_numpy()

# 6. Métricas
mae = mean_absolute_error(actual, predictions)
rmse = np.sqrt(mean_squared_error(actual, predictions))
wape = (
    np.abs(actual - predictions).sum() / np.abs(actual).sum() * 100
    if np.abs(actual).sum() > 0 else float("nan")
)

print("\n========== RESULTADOS XGBOOST ==========")
print(f"Run ID: {RUN_ID}")
print(f"Entrenamiento: {train['semana'].min().date()} a {train['semana'].max().date()}")
print(f"Prueba:        {test_start.date()} a {test_end.date()}")
print(f"Filas train:   {len(train)}")
print(f"Filas test:    {len(test)}")
print(f"MAE:           {mae:.4f}")
print(f"RMSE:          {rmse:.4f}")
print(f"WAPE:          {wape:.4f}%")

# 7. Crear tablas nuevas si no existen
metrics_schema = [
    bigquery.SchemaField("run_id", "STRING"),
    bigquery.SchemaField("model_name", "STRING"),
    bigquery.SchemaField("evaluated_at", "TIMESTAMP"),
    bigquery.SchemaField("metric", "STRING"),
    bigquery.SchemaField("value", "FLOAT"),
    bigquery.SchemaField("target", "STRING"),
    bigquery.SchemaField("split_start", "DATE"),
    bigquery.SchemaField("split_end", "DATE"),
    bigquery.SchemaField("n_test_rows", "INTEGER"),
    bigquery.SchemaField("feature_set", "STRING"),
    bigquery.SchemaField("model_params", "STRING"),
    bigquery.SchemaField("evaluation_type", "STRING"),
]

predictions_schema = [
    bigquery.SchemaField("run_id", "STRING"),
    bigquery.SchemaField("semana", "DATE"),
    bigquery.SchemaField("categoria", "STRING"),
    bigquery.SchemaField("actual", "INTEGER"),
    bigquery.SchemaField("prediccion", "FLOAT"),
    bigquery.SchemaField("error_absoluto", "FLOAT"),
]

for table_id, schema in [
    (METRICS_TABLE, metrics_schema),
    (PREDICTIONS_TABLE, predictions_schema)
]:
    try:
        client.get_table(table_id)
    except Exception:
        client.create_table(bigquery.Table(table_id, schema=schema))
        print(f"Tabla creada: {table_id}")

evaluated_at = datetime.now(timezone.utc).isoformat()

metric_rows = []
for name, value in [
    ("MAE", float(mae)),
    ("RMSE", float(rmse)),
    ("WAPE", float(wape))
]:
    metric_rows.append({
        "run_id": RUN_ID,
        "model_name": "XGBoost",
        "evaluated_at": evaluated_at,
        "metric": name,
        "value": value,
        "target": "lineas_articulo",
        "split_start": test_start.date().isoformat(),
        "split_end": test_end.date().isoformat(),
        "n_test_rows": len(test),
        "feature_set": json.dumps(features),
        "model_params": json.dumps(params),
        "evaluation_type": "new_reproducible_backtest"
    })

metric_errors = client.insert_rows_json(METRICS_TABLE, metric_rows)
if metric_errors:
    raise RuntimeError(f"Error registrando métricas: {metric_errors}")

prediction_rows = []
for (_, row), prediction in zip(test.iterrows(), predictions):
    prediction_rows.append({
        "run_id": RUN_ID,
        "semana": row["semana"].date().isoformat(),
        "categoria": str(row["categoria"]),
        "actual": int(row["lineas_articulo"]),
        "prediccion": float(prediction),
        "error_absoluto": float(abs(row["lineas_articulo"] - prediction))
    })

for start in range(0, len(prediction_rows), 500):
    errors = client.insert_rows_json(
        PREDICTIONS_TABLE,
        prediction_rows[start:start + 500]
    )
    if errors:
        raise RuntimeError(f"Error registrando predicciones: {errors}")

print("\n========== REGISTRO COMPLETADO ==========")
print(f"Métricas:     {METRICS_TABLE}")
print(f"Predicciones: {PREDICTIONS_TABLE}")
print(f"Run ID:       {RUN_ID}")
