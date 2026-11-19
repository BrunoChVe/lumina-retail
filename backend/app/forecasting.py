import math
import numpy as np

def calc_metrics(actual, pred):
    if not actual or not pred or len(actual) != len(pred):
        return None, None, None
    actual = np.array(actual)
    pred = np.array(pred)
    mae = np.mean(np.abs(actual - pred))
    rmse = np.sqrt(np.mean((actual - pred)**2))
    sum_actual = np.sum(np.abs(actual))
    wape = (np.sum(np.abs(actual - pred)) / sum_actual * 100) if sum_actual > 0 else 0.0
    return round(mae, 2), round(rmse, 2), round(wape, 2)

def naive_forecast(series, horizon=1):
    if not series: return []
    last_val = series[-1]
    return [last_val] * horizon

def moving_average_forecast(series, k=4, horizon=1):
    if len(series) < k: return []
    ma = np.mean(series[-k:])
    return [ma] * horizon

def croston_forecast(series, horizon=1, alpha=0.1):
    # Croston's method for intermittent demand
    if not series: return []
    
    # Initialize
    y = series[0] if series[0] > 0 else 1.0 # demand size
    p = 1.0 # interval
    q = 1.0 # time since last demand
    
    for t in range(1, len(series)):
        z = series[t]
        if z > 0:
            y = alpha * z + (1 - alpha) * y
            p = alpha * q + (1 - alpha) * p
            q = 1.0
        else:
            q += 1.0
            
    forecast_val = y / p if p > 0 else 0
    return [forecast_val] * horizon

def simple_exponential_smoothing(series, horizon=1, alpha=0.3):
    if not series: return []
    s = series[0]
    for t in range(1, len(series)):
        s = alpha * series[t] + (1 - alpha) * s
    return [s] * horizon

def evaluate_models(series, horizon):
    # Evaluamos en un holdout set de tamaño 'horizon' si hay suficientes datos
    # Minimo historial para holdout: horizon * 2
    if len(series) < horizon * 2:
        return None
        
    train = series[:-horizon]
    test = series[-horizon:]
    
    results = []
    
    # 1. Naive
    pred_naive = naive_forecast(train, horizon)
    mae, rmse, wape = calc_metrics(test, pred_naive)
    results.append({"model": "Naive (t-1)", "mae": mae, "rmse": rmse, "wape": wape, "pred_last": pred_naive[-1]})
    
    # 2. Moving Average (k=4)
    pred_ma = moving_average_forecast(train, k=4, horizon=horizon)
    mae, rmse, wape = calc_metrics(test, pred_ma)
    results.append({"model": "Media Móvil (k=4)", "mae": mae, "rmse": rmse, "wape": wape, "pred_last": pred_ma[-1]})
    
    # 3. Simple Exponential Smoothing
    pred_ses = simple_exponential_smoothing(train, horizon=horizon)
    mae, rmse, wape = calc_metrics(test, pred_ses)
    results.append({"model": "Exponential Smoothing", "mae": mae, "rmse": rmse, "wape": wape, "pred_last": pred_ses[-1]})
    
    # 4. Croston (si hay muchos ceros)
    ceros = sum(1 for x in train if x == 0)
    if ceros > len(train) * 0.2: # Más del 20% de ceros
        pred_cros = croston_forecast(train, horizon=horizon)
        mae, rmse, wape = calc_metrics(test, pred_cros)
        results.append({"model": "Croston (Intermitente)", "mae": mae, "rmse": rmse, "wape": wape, "pred_last": pred_cros[-1]})
        
    # 5. Seasonal Naive (t-52)
    if len(train) >= 52 + horizon:
        pred_snaive = train[-52:-52+horizon]
        mae, rmse, wape = calc_metrics(test, pred_snaive)
        results.append({"model": "Seasonal Naive (t-52)", "mae": mae, "rmse": rmse, "wape": wape, "pred_last": pred_snaive[-1]})

    # Ordenar por WAPE
    results.sort(key=lambda x: x["wape"])
    return results

def get_best_forecast(series, horizon):
    evals = evaluate_models(series, horizon)
    if not evals:
        # Fallback a Moving average si no hay para holdout pero sí hay datos
        if len(series) >= 4:
            pred = moving_average_forecast(series, k=4, horizon=horizon)
            return {"model": "Media Móvil (k=4) - Sin Backtest", "forecast": pred, "evals": []}
        else:
            return None
            
    best = evals[0]
    model_name = best["model"]
    
    # Generar pronóstico final con toda la serie
    if model_name == "Naive (t-1)":
        pred = naive_forecast(series, horizon)
    elif model_name == "Media Móvil (k=4)":
        pred = moving_average_forecast(series, k=4, horizon=horizon)
    elif model_name == "Exponential Smoothing":
        pred = simple_exponential_smoothing(series, horizon)
    elif model_name == "Croston (Intermitente)":
        pred = croston_forecast(series, horizon)
    elif model_name == "Seasonal Naive (t-52)":
        if len(series) >= 52:
            pred = [series[-52 + i % 52] for i in range(horizon)]
        else:
            pred = moving_average_forecast(series, k=4, horizon=horizon)
    else:
        pred = naive_forecast(series, horizon)
        
    return {
        "model": model_name,
        "forecast": pred,
        "evals": evals
    }
