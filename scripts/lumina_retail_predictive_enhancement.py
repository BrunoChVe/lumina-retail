import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timezone
from google.cloud import bigquery
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Conexión a BigQuery
client = bigquery.Client(project='lumina-retail-001')

def load_data():
    query = """
    SELECT semana, categoria, ingresos as total_sales, lineas_articulo as total_items
    FROM `lumina-retail-001.lumina_stage.gold_demand_olist_weekly`
    ORDER BY categoria, semana
    """
    df = client.query(query).to_dataframe()
    df['semana'] = pd.to_datetime(df['semana'])
    return df

def feature_engineering(df):
    df = df.sort_values(['categoria', 'semana']).copy()
    
    # Lags y medias móviles (hasta 4 semanas)
    df['lag_1'] = df.groupby('categoria')['total_items'].shift(1)
    df['rolling_mean_4'] = df.groupby('categoria')['lag_1'].transform(lambda x: x.rolling(window=4, min_periods=1).mean())
    df['rolling_mean_8'] = df.groupby('categoria')['lag_1'].transform(lambda x: x.rolling(window=8, min_periods=1).mean())
    df['month'] = df['semana'].dt.month
    df['week_of_year'] = df['semana'].dt.isocalendar().week
    
    # Seasonal Lag (t-52)
    df['lag_52'] = df.groupby('categoria')['total_items'].shift(52)
    
    df = df.dropna(subset=['lag_1'])
    return df

def calculate_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    sum_actual = np.sum(y_true)
    wape = (np.sum(np.abs(y_true - y_pred)) / sum_actual) * 100 if sum_actual > 0 else 0
    return mae, rmse, wape

def evaluate_models():
    print("Iniciando carga de datos...")
    df = load_data()
    print("Ingeniería de características...")
    df = feature_engineering(df)
    
    split_date = pd.to_datetime('2018-06-11')
    train = df[df['semana'] < split_date].copy()
    test = df[df['semana'] >= split_date].copy()
    
    print(f"Train set: {len(train)} rows")
    print(f"Test set: {len(test)} rows (888 expected)")
    
    results = []
    
    # 1. Naive Baseline (t-1)
    test['pred_naive'] = test['lag_1']
    mae_n, rmse_n, wape_n = calculate_metrics(test['total_items'], test['pred_naive'])
    results.append({'model': 'Naive (t-1)', 'mae': mae_n, 'rmse': rmse_n, 'wape': wape_n})
    
    # 2. Seasonal Naive (t-52)
    test['pred_snaive'] = test['lag_52'].fillna(test['lag_1']) 
    mae_sn, rmse_sn, wape_sn = calculate_metrics(test['total_items'], test['pred_snaive'])
    results.append({'model': 'Seasonal Naive (t-52)', 'mae': mae_sn, 'rmse': rmse_sn, 'wape': wape_sn})
    
    # 3. LightGBM
    try:
        import lightgbm as lgb
        features = ['lag_1', 'rolling_mean_4', 'rolling_mean_8', 'month', 'week_of_year']
        target = 'total_items'
        model_lgb = lgb.LGBMRegressor(n_estimators=100, max_depth=3, learning_rate=0.03, random_state=42, verbose=-1)
        model_lgb.fit(train[features], train[target])
        test['pred_lgb'] = model_lgb.predict(test[features])
        test['pred_lgb'] = np.clip(test['pred_lgb'], 0, None)
        mae_l, rmse_l, wape_l = calculate_metrics(test['total_items'], test['pred_lgb'])
        results.append({'model': 'LightGBM', 'mae': mae_l, 'rmse': rmse_l, 'wape': wape_l})
    except ImportError:
        print("LightGBM no instalado")
        
    for r in results:
        print(f"Modelo: {r['model']:<25} | WAPE: {r['wape']:.2f}% | MAE: {r['mae']:.2f} | RMSE: {r['rmse']:.2f}")
    
    ml_models = [r for r in results if r['model'] not in ('Naive (t-1)', 'Seasonal Naive (t-52)')]
    best_ml = min(ml_models, key=lambda x: x['wape'])
    
    col_pred = 'pred_lgb'
    
    run_id = str(uuid.uuid4())
    evaluated_at = datetime.now(timezone.utc).isoformat()
    split_start_str = '2018-06-11'
    split_end_str = test['semana'].max().strftime('%Y-%m-%d')
    n_test_rows = len(test)
    
    metrics_data = [
        {"run_id": run_id, "model_name": best_ml['model'], "metric": "MAE", "value": best_ml['mae'], "target": "lineas_articulo", "split_start": split_start_str, "split_end": split_end_str, "n_test_rows": n_test_rows, "evaluated_at": evaluated_at, "evaluation_type": "BACKTEST"},
        {"run_id": run_id, "model_name": best_ml['model'], "metric": "RMSE", "value": best_ml['rmse'], "target": "lineas_articulo", "split_start": split_start_str, "split_end": split_end_str, "n_test_rows": n_test_rows, "evaluated_at": evaluated_at, "evaluation_type": "BACKTEST"},
        {"run_id": run_id, "model_name": best_ml['model'], "metric": "WAPE", "value": best_ml['wape'], "target": "lineas_articulo", "split_start": split_start_str, "split_end": split_end_str, "n_test_rows": n_test_rows, "evaluated_at": evaluated_at, "evaluation_type": "BACKTEST"}
    ]
    
    preds_data = []
    for _, row in test.iterrows():
        preds_data.append({
            "run_id": run_id,
            "semana": row['semana'].strftime('%Y-%m-%d'),
            "categoria": row['categoria'],
            "actual": float(row['total_items']),
            "prediccion": float(row[col_pred]),
            "error_absoluto": float(abs(row['total_items'] - row[col_pred]))
        })
    
    print("Guardando métricas y predicciones en lumina_stage...")
    client.insert_rows_json("lumina-retail-001.lumina_stage.model_evaluation_metrics", metrics_data)
    for i in range(0, len(preds_data), 500):
        client.insert_rows_json("lumina-retail-001.lumina_stage.model_evaluation_predictions", preds_data[i:i+500])
        
    print(f"Completado. Run ID: {run_id}")
    return run_id

if __name__ == '__main__':
    evaluate_models()
