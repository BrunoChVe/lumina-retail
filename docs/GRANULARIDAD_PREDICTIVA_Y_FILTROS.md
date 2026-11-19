# GRANULARIDAD PREDICTIVA Y FILTROS POR TIENDA Y PRODUCTO
**Plataforma LUMINA Retail — Demand Forecasting & Machine Learning Architecture**

---

## 1. Auditoría del Modelo de Datos y Dimensiones por Fuente

Al examinar los esquemas y las fuentes disponibles en BigQuery (`lumina_stage` y `lumina_sandbox`), se identificó la siguiente disponibilidad dimensional real:

| Fuente de Datos | Moneda | Dimensión de Tienda / Unidad Comercial | Dimensión de Vendedor | Dimensión de Producto | Dimensión Geográfica | Granularidad Predictiva Soportada |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| **Olist (Brasil)** | BRL | Unidad Comercial General (Marketplace Olist) | `seller_id` (3,095 vendedores únicos en `fact_order_items`) | `product_id` (32,951 productos) / `categoria` (74 categorías) | Estado / Región cliente | **Categoría (Gold ML XGBoost)** / **Vendedor-Producto** (cuando $\ge 10$ semanas) |
| **TheLook eCommerce** | USD | Tienda Global eCommerce (Canal Digital Internacional) | No aplica (modelo B2C directo) | Catálogo sintético de moda | Centros de distribución / Países de clientes | **Tienda Global** (sin serie estacional Gold entrenada) |
| **UCI Online Retail** | GBP | **Sin tiendas físicas**. Log transaccional directo | No aplica (comercio B2B/B2C minorista de UK) | `StockCode` (3,941 SKUs activos) | `Country` (38 países / mercados) | **País / Mercado y Producto** (Demanda empírica histórica) |

### Regla Metodológica Fundamental
- **No inventar tiendas físicas:** No se fuerza un atributo ficticio `store_id` para fuentes que no disponen de locales físicos reales.
- Para **Olist**, la unidad comercial desagregada corresponde al vendedor del marketplace (`seller_id`).
- Para **UCI**, la unidad de segmentación corresponde al **País / Mercado Geográfico** (`country`).
- Para **TheLook**, se presenta como **Tienda Digital Global**.

---

## 2. Granularidad del Modelo Predictivo en Producción (XGBoost)

### Modelo Productivo en Gold WAP
- **Tabla:** `lumina_sandbox.gold_predictive_predictions`
- **Nivel de Entrenamiento:** **Categoría de Producto** (`categoria`), sobre el panel semanal completo de Olist (103 semanas, 74 categorías).
- **Ventana de Evaluación (Backtest):** Últimas 12 semanas (888 observaciones en total: 74 categorías × 12 semanas).
- **Métricas Oficiales Aprobadas en Auditoría WAP:**
  - **MAE:** 7.78
  - **RMSE:** 16.72
  - **WAPE:** 36.60%

### Criterio de Suficiencia de Historial (Mínimo 10 Semanas)
Al desagregar la demanda a nivel de **Vendedor-Producto** (`seller_id` + `product_id` en Olist) o **País-Producto** (`country` + `StockCode` en UCI), la gran mayoría de las combinaciones presenta **demanda sumamente intermitente o esparcida** (promedio de 3.2 items por combinación sobre dos años completos).

Para garantizar validez analítica y prevenir pronósticos espurios:
1. **Combinaciones con Historial Suficiente ($\ge 10$ semanas activas):**
   - Se calcula la serie temporal semanal histórica.
   - Se proyecta la demanda esperada (`prediccion`) junto a intervalos de confianza estadísticos al 95%:
     $$\text{Límite Superior} = \text{Predicción} + 1.96 \cdot \sigma$$
     $$\text{Límite Inferior} = \max(0, \text{Predicción} - 1.96 \cdot \sigma)$$
   - Se calculan los indicadores de tendencia (**CRECIENTE**, **ESTABLE**, **DECRECIENTE**) y variabilidad ($\sigma$).
2. **Combinaciones con Historial Insuficiente ($< 10$ semanas activas):**
   - El sistema **evita generar pronósticos sintéticos artificiales**.
   - Devuelve un estado controlado:
     ```json
     {
       "sufficient_history": false,
       "observations": 3,
       "reason": "Historial insuficiente para pronóstico estadístico confiable (Encontradas 3 semanas de actividad, mínimo requerido: 10 semanas)."
     }
     ```
   - La interfaz de usuario muestra un banner de advertencia metodológica en color ámbar/dorado, presentando únicamente los datos reales observados.

---

## 3. Endpoints Implementados en FastAPI

### `GET /api/predictive/metadata`
Retorna metadatos para poblar dinámicamente los selectores dependientes en el frontend:
- Fuentes disponibles con sus divisas y tipos de granularidad.
- Lista de 74 categorías en el modelo Gold de XGBoost.
- Lista de los 15 vendedores con mayor actividad en Olist (`seller_id`, productos asociados, volumen de transacciones).
- Lista de los 15 productos con mayor rotación en Olist.
- Lista de países y productos más representativos en UCI.

### `GET /api/predictive/forecast`
Endpoint unificado para pronóstico granular por categoría, tienda, vendedor o producto:
- **Parámetros:**
  - `source`: `'olist'`, `'thelook'`, `'uci'` (por defecto: `'olist'`).
  - `category`: Nombre de la categoría (ej. `'bed_bath_table'`).
  - `seller_id`: Identificador de vendedor de Olist.
  - `product_id`: SKU de producto (`product_id` en Olist o `StockCode` en UCI).
  - `country`: País para la fuente UCI (ej. `'United Kingdom'`).
  - `horizon`: Semanas a proyectar (4, 8 o 12 semanas).
- **Respuesta:**
  - `sufficient_history`: Booleano que certifica si se superó el umbral estadístico.
  - `avg_demand`: Demanda promedio por semana.
  - `variability_std`: Desviación estándar observada ($\sigma$).
  - `trend`: Dirección de la tendencia.
  - `metrics`: MAE, RMSE y WAPE.
  - `history`: Serie temporal real observada (`[{ semana, actual }]`).
  - `forecast`: Serie pronosticada con bandas de incertidumbre (`[{ semana, prediccion, lower_bound, upper_bound }]`).
  - `note`: Explicación metodológica de la técnica aplicada.

---

## 4. Visualización en el Frontend (`Predictive.jsx`)

1. **Barra de Filtros Dependientes:**
   - Selector de Fuente (Olist, TheLook, UCI).
   - Selector de Nivel de Segmentación: *Por Categoría (Modelo Gold)* vs. *Por Vendedor y Producto*.
   - Selector reactivo: Al cambiar a *Por Vendedor y Producto*, se despliegan automáticamente los selectores de `seller_id` y `product_id`.
   - Selector de Horizonte: 4 semanas (1 mes), 8 semanas (2 meses), 12 semanas (1 trimestre).
2. **Tarjeta de Resultados Granulares:**
   - 4 tarjetas métricas contextuales: Demanda Promedio, Tendencia Reciente (color dinámico), Variabilidad ($\pm\sigma$), Observaciones y WAPE.
3. **Gráfico de Serie Temporal e Intervalos de Confianza:**
   - Renderizado con Recharts mostrando 4 series:
     - Línea azul sólida: Demanda Real Histórica.
     - Línea verde sólida con puntos: Demanda Pronosticada.
     - Línea verde punteada: Límite Superior del 95% ($+1.96\sigma$).
     - Línea amarilla punteada: Límite Inferior del 95% ($-1.96\sigma$).
4. **Manejo de Casos con Historial Insuficiente:**
   - Presentación de alerta visual clara con iconografía de advertencia, impidiendo la generación de demanda ficticia para combinaciones esparcidas.
