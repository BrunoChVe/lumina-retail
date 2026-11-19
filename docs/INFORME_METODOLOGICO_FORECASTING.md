# INFORME METODOLÓGICO DE FORECASTING

## 1. Fundamentos y Objetivos
LUMINA Retail aplica métodos de pronóstico estadístico y Machine Learning para estimar la demanda futura en múltiples granularidades. El objetivo es proporcionar herramientas matemáticas de soporte para la toma de decisiones logísticas, evitando el sobre-inventario y minimizando el riesgo de ruptura de stock (Out of Stock).

## 2. Modelos Implementados
La plataforma combina dos enfoques principales según el nivel de agregación:

### 2.1. Modelos Globales y de Machine Learning (Nivel Categoría)
Entrenados offline y gobernados bajo el protocolo **WAP-02.1**.
- **XGBoost Regressor:** Utilizado para demanda estacional agregada por categoría en Olist. Extrae relaciones no lineales utilizando features de lags (t-1, t-4, t-8, t-12).
- **Seasonal Naive (t-52):** Baseline para series con marcada estacionalidad anual.
- **Naive Baseline (t-1):** Heurística de persistencia. En categorías de rotación estable y altamente autocorrelacionadas ha demostrado competitividad frente a XGBoost en la métrica MAE.

### 2.2. Modelos Heurísticos Dinámicos (Nivel SKU/Geografía)
Calculados *on-the-fly* mediante la API (`backend/app/forecasting.py`) para segmentaciones atómicas donde entrenar XGBoost por cada par Vendedor-Producto generaría sobreajuste extremo:
- **Media Móvil (Moving Average, k=4):** Suaviza el ruido en series estables de alta rotación.
- **Exponential Smoothing:** Asigna pesos decrecientes exponencialmente, otorgando mayor relevancia a la historia reciente sin perder la inercia general de la serie.
- **Croston Method:** Especializado en **demanda intermitente**. Si una serie temporal presenta más de un 20% de ceros en su historial, LUMINA automáticamente selecciona el algoritmo de Croston (separando la estimación del tamaño de la demanda de la probabilidad temporal de que esta ocurra).

## 3. Backtesting y Validación Temporal
El marco metodológico repudia estrictamente las particiones aleatorias (*random split* / *k-fold* tradicional) en series temporales para evitar **Data Leakage**.

- **Validación en Backend Dinámico:** Se aplica un holdout asimétrico. Los últimos *N* periodos (determinados por el parámetro `horizonte`) se reservan como conjunto de prueba (*test set*). El algoritmo entrena todos los modelos heurísticos sobre la fracción histórica inicial y selecciona automáticamente aquel que minimice el WAPE en el horizonte de validación.

## 4. Métricas de Evaluación Utilizadas
- **MAE (Mean Absolute Error):** Magnitud promedio del error en las unidades de la serie original. Sensible a valores extremos.
- **RMSE (Root Mean Square Error):** Penaliza severamente desviaciones grandes, ideal para dimensionar colchones de seguridad de inventario.
- **WAPE (Weighted Absolute Percentage Error):** Métrica principal de decisión. Se prefiere sobre MAPE dado que WAPE tolera valores reales iguales a cero (comunes en retail desagregado) agregando el volumen total.

## 5. Estimación de Incertidumbre
Las bandas de intervalo en los gráficos de LUMINA representan un **Intervalo de Confianza del 95%** teórico, formulado asintóticamente como $\pm 1.96\sigma$, asumiendo distribución normal en los residuales fuera de muestra.

## 6. Limitaciones Metodológicas
- **Falta de Profundidad en UCI:** UCI Online Retail cuenta con apenas 53 semanas de historia. Esto impide matemáticamente estimar estacionalidades interanuales (Lags > 52 semanas). LUMINA fuerza el uso de modelos de media móvil y suavizado exponencial y deshabilita algoritmos estacionales.
- **Restricción de Densidad:** No se pronostica bajo ningún modelo matemático ninguna segmentación SKU/Región que no acredite al menos 10 semanas de actividad comercial (Criterio Anti-Ruido).
