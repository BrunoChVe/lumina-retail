# INFORME FINAL DE LUMINA RETAIL
**Proyecto Integral de Ingeniería y Ciencia de Datos | Inteligencia de Demanda y Telemetría Operativa**  

---

## 1. Resumen Ejecutivo
LUMINA Retail es una plataforma cloud-native que consolida un pipeline transaccional *end-to-end* (Batch y Streaming) para gobernar un ecosistema e-commerce heterogéneo (Olist, TheLook y UCI). El proyecto unificó con éxito un Data Warehouse en BigQuery (separando estricta e inmutablemente las divisas BRL, USD y GBP), e introdujo un modelo algorítmico reactivo de Machine Learning (XGBoost) para pronosticar demanda macro, empalmándolo con un recomendador heurístico atómico (*on-the-fly*) para SKUs individuales. 
Para simular el impacto operativo de esta demanda, se desarrolló e integró un *Centro de Simulación de Cyber Days*, con orquestación distribuida (Kafka & Dataproc) sobre un dashboard moderno construido en React/Vite.

---

## 2. Fuentes de Datos y Aislamiento Multidivisa
El modelado de datos garantizó la autonomía transaccional sin caer en conversiones ficticias que contaminen los márgenes brutos.
- **Olist (Brasil):** Operativo y Logístico (SLA, Tiempos de despacho). Moneda: **BRL**. Nivel: Seller/Product.
- **TheLook (Global):** Comercial Sintético (B2C). Moneda: **USD**.
- **UCI Online Retail (UK):** Histórico analítico sin locales físicos y sin logística de despachos documentada en la fuente. Moneda: **GBP**. Nivel: País/Product (StockCode). Se derivaron taxonómicamente sus categorías usando un motor REGEX.

---

## 3. Gobernanza de Arquitectura Medallion (WAP)
La consolidación ELT a las tablas consumibles `gold_` se blindó bajo el protocolo lógico **WAP-02.1 (Write-Audit-Publish)**:
- 16 pruebas automatizadas corren sobre una rama clónica (`lumina_sandbox`) antes de autorizar el commit lógico de la transacción analítica.
- El sistema de bloqueo transaccional protege al pipeline contra escrituras concurrentes.

---

## 4. Analítica Predictiva y Modelado de Demanda (Forecasting)
Para habilitar una planificación proactiva, LUMINA evalúa el forecasting desde dos enfoques metodológicos complementarios:

### 4.1. Nivel Macro: Modelo Categoría (Machine Learning)
Se entrenó offline un **XGBoost Regressor** para cada una de las 74 categorías base de Olist aprovechando la profundidad de la data (103 semanas, ventana de backtest de 888 observaciones en 12 semanas). El modelo aprendió interacciones de rezagos estacionales (Lags 1, 4, 8, 12).
* **Métricas Validadas (RMSE: 16.72, WAPE: 36.60%).** 
* Se comparó frente al heurístico de inercia *Naive t-1*, que entregó métricas ligeramente superiores a corto plazo (RMSE: 15.90, WAPE: 35.49%) dada la altísima autocorrelación de la data agregada. *Seasonal Naive* fue descartado metodológicamente por subestimar bruscamente la serie en periodos de alto crecimiento comercial interanual.

### 4.2. Nivel Atómico: Modelos Heurísticos Dinámicos (SKU/Geografía)
Al descender la granularidad a un Par Vendedor-Producto o País-Producto, la serie temporal se vuelve esparcida y volátil. 
- **La Solución:** La API de FastAPI ejecuta una competencia matemática instantánea frente a cada petición HTTP (`/api/predictive/forecast`). 
- Divide el histórico local en un holdout dinámico y entrena concurrentemente: *Media Móvil*, *Suavizado Exponencial (SES)*, *Croston* (para series intermitentes con muchos ceros) y *Naive*. El motor escoge el de menor WAPE y traza un **Intervalo de Confianza del 95%** paramétrico ($\pm 1.96\sigma$).
- **Salvaguarda Estadística:** LUMINA Retail no se inventa datos. Si un SKU carece de al menos **10 semanas de actividad** reportada, rechaza la invocación y alerta visualmente de la escasez muestral en la interfaz.

### 4.3. Restricción sobre UCI Online Retail
Se canceló metodológicamente entrenar modelos de estacionalidad multianual (t-52) sobre UCI debido a la carencia estructural de masa de datos (sólo cuenta con **53 semanas** operativas totales).

---

## 5. Simulación Operativa de Alta Demanda (Cyber Days)
Para proyectar cómo respondería el stock ante escenarios promocionales modelados por los algoritmos anteriores, LUMINA posee un Simulador de Ciclo de Pedidos (Order Lifecycle).

- **Inyección de Tráfico:** Un script nativo genera estrés en un clúster *Apache Kafka* (VM `lumina-kafka-vm`) alcanzando *bursts* sintéticos (ej. 795 eventos, picos de 50 requests/s).
- **Procesamiento Reactivo:** Apache Spark en un clúster *Dataproc* (12 vCPUs) absorbe la carga mediante un `writeStream` de micro-lotes (5s) contra *Google Cloud Storage* y *BigQuery*, confirmando atómicamente el checkpoint en HDFS y deduplicando el saldo analíticamente.
- **Aislamiento Seguro:** Todo el ruido inducido viaja etiquetado (`synthetic_flag = true`, Región = `CYBER_TEST`). Los KPIs comerciales históricos no se ven tocados en un 0%.
- **Módulo de Reacción Frontend:** El *Centro de Simulación* (React) grafica el stock de impacto frente a 3 escenarios: *Base* (demanda del modelo), *Moderado (+20%)* y *Intensivo (+50%)*, previniendo el desabastecimiento o emitiendo fallas "Out of Stock" lógicas si el stock remanente cae bajo el límite de reserva.

---

## 6. Despliegue de Aplicación (Cloud Run) e IAP
El producto final se encuentra paquetizado en un contenedor multi-etapa ejecutado como un servicio Serverless (`lumina-retail`) en la región `us-central1`. Se escala a cero y está totalmente resguardado contra la red abierta a través del protocolo seguro de Google Cloud **Identity-Aware Proxy (IAP)**, permitiendo accesos logados bajo OIDC.

---

## 7. Costos, Mantenimiento y Conclusión
- Para proteger el entorno, la virtualización paralela del Big Data (VM Kafka y Nodos Dataproc) se ha ordenado **apagar (TERMINATED)**. 
- LUMINA Retail no posee gastos ocultos concurrentes, apoyándose nativamente sobre BigQuery Serverless y Cloud Run, con un frontend que transpila un PDF profesional (`@media print`) permitiendo compartir reportes analíticos y matemáticos de las proyecciones a los tomadores de decisiones de inventario con nulo cargo de infraestructura.

El proyecto es reproducible y sus arquitecturas están rigurosamente probadas (*75 pruebas Unitarias pytest / 100% Passed*), cumplimentando el espectro completo de la ciencia e ingeniería de datos en una sola solución funcional lista para defensa técnica.
