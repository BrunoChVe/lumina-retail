# REFERENCIA API - MÓDULO PREDICTIVE

El backend de FastAPI expone la lógica predictiva analítica e inteligente a través de 3 endpoints de alto rendimiento localizados bajo el prefijo `/api/predictive/*`.

## 1. `GET /api/predictive/metadata`
**Propósito:** Provee los catálogos lógicos para construir selectores dependientes en el Frontend.
- **Retorno JSON:**
  - `sources`: Arreglo de orígenes de datos (olist, thelook, uci).
  - `categories`: Arreglo de 74 categorías evaluadas en XGBoost.
  - `top_sellers`: Las 15 tiendas con mayor cantidad de productos en Olist.
  - `top_products`: Los 15 SKUs más vendidos globalmente en Olist.
  - `uci_countries`: Países europeos operados en UCI Online Retail.
  - `uci_top_products`: SKUs más consumidos históricamente en UCI.

## 2. `GET /api/predictive/metrics`
**Propósito:** Recupera las métricas de rendimiento del backtest offline publicado y asegurado por WAP en BigQuery.
- **Retorno JSON:** Arreglo de registros físicos tomados de `gold_predictive_metrics` (RMSE, MAE, WAPE) por cada algoritmo evaluado durante el pre-procesamiento del Data Engineer.

## 3. `GET /api/predictive/predictions`
**Propósito:** Retorna la curva combinada histórica y proyectada (Actual vs Forecast) para los modelos agregados.
- **Parámetros:**
  - `categoria` (Opcional): Filtro de string para una de las 74 categorías de Olist.

## 4. `GET /api/predictive/forecast`
**Propósito:** Motor atómico (Online) de pronóstico de series temporales de alta granularidad. En base a los parámetros recibidos, cruza el Warehouse (Olist/UCI), recupera la serie temporal nativa a nivel SKU y evalúa en un holdout dinámico los modelos *Media Móvil, Exponential Smoothing, Croston, Naive y Seasonal Naive*, devolviendo el ganador.
- **Parámetros GET:**
  - `source`: olist | uci | thelook
  - `category`: String de categoría (Solo para Olist macro).
  - `seller_id`: GUID del vendedor (Solo para Olist granular).
  - `product_id`: SKU del producto o StockCode.
  - `country`: Nombre del mercado (Solo para UCI).
  - `horizon`: Integer (Rango seguro de 1 a 52).
- **Control de Error Estadístico:** 
  Si el cruce en BigQuery retorna menos de 10 semanas operativas, el motor no realizará cálculos de Machine Learning ni pronóstico, devolviendo de inmediato `sufficient_history: false` junto a la serie original para pintar la gráfica con la excepción respectiva.
- **Estructura JSON (Éxito):**
  - `sufficient_history`: true
  - `model_name`: Nombre del algoritmo matemático seleccionado por el menor WAPE.
  - `avg_demand`, `variability_std`, `trend`: Indicadores de tendencia simple.
  - `metrics`: { MAE, RMSE, WAPE }
  - `models_evals`: Diccionario del ranking del backtest contra todos los demás métodos calculados on-the-fly.
  - `history`: Arreglo de los `[horizonte]` últimos puntos empíricos.
  - `forecast`: Arreglo de los `[horizon]` siguientes puntos de pronóstico con `prediccion`, `lower_bound`, `upper_bound`.
