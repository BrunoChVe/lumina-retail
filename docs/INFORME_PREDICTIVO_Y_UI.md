# LUMINA Retail: Informe Predictivo, Store Performance y Rediseño Premium SaaS

**Proyecto:** LUMINA Retail (RetailSmart Data Platform)  
**Autor:** Bruno Chihuán Velásquez  
**Revisión Productiva:** `wap-gold-final` (Cloud Run)  

---

## 1. Evolución del Modelo Predictivo de Demanda (Machine Learning)

El pipeline de ML ha sido sometido a una profunda revisión mediante ingeniería de características y experimentación algorítmica.

### 1.1. Ingeniería de Características (Feature Engineering)
Para mejorar la captura de autocorrelación y estacionalidad se implementaron las siguientes variables en un modelo ensamblado sobre el histórico de Olist (2016-2018):
- Retardos Temporales (Lags): `lag_1` (Autoregresivo T-1).
- Suavizado Histórico (Rolling Means): `rolling_mean_4`, `rolling_mean_8` sobre el lag.
- Descomposición de Calendario: `month`, `week_of_year`.

### 1.2. Benchmark Académico Actualizado (888 Observaciones)

| Modelo | Clasificación | MAE | RMSE | WAPE (%) | Estado de Despliegue |
|---|---|---:|---:|---:|:---:|
| **Naive Baseline ($t-1$)** | Heurístico (Persistencia) | 7.54 | 15.90 | 35.49% | Benchmark Óptimo |
| **LightGBM Regressor** | Supervisado (Gradient Boosting) | 7.72 | 16.08 | 36.34% | **Publicado en Gold** |
| **XGBoost Regressor** | Supervisado (Anterior) | 7.78 | 16.72 | 36.60% | Descartado |
| **Seasonal Naive ($t-52$)** | Heurístico (Estacional Anual) | 12.79 | 27.18 | 60.21% | Descartado (Sesgo) |

**Mejora Consolidada:** Se migró el estimador productivo de XGBoost a LightGBM, logrando una reducción del error porcentual absoluto ponderado del 36.60% al 36.34%, acercándose de manera consistente al óptimo teórico representado por la inercia inmediata de la persistencia ($t-1$).

Las predicciones fueron aprobadas por las auditorías WAP (`TEST_PRED_NO_NEGATIVE_PREDS`, `TEST_PRED_METRICS_EXIST`, `TEST_PRED_VALID_DATES`) y publicadas en `gold_predictive_metrics`.

---

## 2. Auditoría del Modelo de Negocio (Las 3 Tiendas Físicas)

Se ejecutó un diagnóstico formal sobre el DW BigQuery:
- **Olist Store (Brasil):** Marketplace descentralizado. Carece de tiendas propias; se distribuye a nivel nacional (Vendedores).
- **TheLook eCommerce:** Cuenta con 10 Centros de Distribución lógicos, no clasificados unívocamente como tres tiendas.
- **UCI Online Retail:** B2B transfronterizo en UK/Europa. Carece de sucursales identificables.

**Resolución Analítica (Modelo Dimensional Limitado):**
Dado el requerimiento, se diseñó la vista `vw_store_dimension` que mapea cada fuente global (Olist, TheLook, UCI) como una de las 3 "tiendas" o unidades operacionales principales. Esto permite habilitar el reporte multitienda (Store Performance) garantizando integridad estadística **sin inventar metadatos geográficos**.

---

## 3. Rediseño Integral de la Interfaz (LUMINA Retail Platform)

La capa de consumo (React 19 / Vite) se actualizó bajo los estándares UX/UI "Premium SaaS":
- **Tema Corporativo Oscuro:** Uso estratégico de fondos *Night Blue* y *Graphite* (`#0b1120`, `#0f172a`), con acentos en colores funcionales (Cian, Esmeralda, Turquesa).
- **Nuevo Módulo de Negocio (Store Performance):** Consola que filtra e integra el rendimiento comercial y las devoluciones calculadas por tienda/fuente, revelando Ventas Brutas vs. Ventas Netas con preservación estricta de Divisa (BRL, USD, GBP).
- **Monitor de Gobernanza:** Despliegue de un badge estático en la barra de control global y en el módulo Predictivo garantizando que los datos visualizados corresponden a la versión "WAP Gold v1.0" activa en el momento de consulta, con visibilidad del cumplimiento de las 16 auditorías exigidas. 
