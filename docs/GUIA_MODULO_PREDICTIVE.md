# GUÍA DE USUARIO: MÓDULO PREDICTIVE

El módulo **Predicción de Demanda** de LUMINA Retail es la herramienta centralizada para evaluar proyecciones estocásticas del consumo, permitiendo su integración con la toma de decisiones logísticas de manera transversal a los Data Sources.

## 1. Menú de Filtros Dependientes y Combinables
Ubicado en el bloque superior, este panel reacciona dinámicamente según la fuente seleccionada:
- **Fuente de Datos:** Elija entre el ecosistema brasileño (Olist, moneda BRL), el global sintético (TheLook, USD) o la operación histórica del Reino Unido (UCI Online Retail, GBP).
- **Nivel de Segmentación:** Para Olist, usted puede consultar el pronóstico macro **Por Categoría** (soportado por el modelo Gold XGBoost), o descender a la granularidad atómica **Por Vendedor y Producto**.
- **País y SKU (Para UCI):** Despliega exclusivamente los 38 mercados de UCI y sus respectivos productos (`StockCode`).
- **Horizonte de Predicción:** Elija visualizar la demanda esperada para 4 semanas (1 mes), 8 semanas (2 meses) o 12 semanas (Trimestre completo).

## 2. Comprensión de los KPIs de Segmento
Una vez solicitada una combinación válida, la plataforma devuelve:
- **Modelo Seleccionado:** Especifica el algoritmo estadístico que el motor de la API seleccionó automáticamente tras realizar el backtest de validación en tiempo real (Ej. *Exponential Smoothing* o *Croston*).
- **Demanda Promedio:** Media de consumo en la ventana histórica.
- **Tendencia Reciente:** Calificación macro visual (`CRECIENTE`, `ESTABLE`, `DECRECIENTE`).
- **WAPE y Variabilidad:** Precisión del modelo en el test set validado y dispersión matemática de la serie.

## 3. Banner de Historial Insuficiente
Si una combinación SKU/Mercado posee menos de **10 semanas de actividad comercial demostrada**, la plataforma bloqueará la generación de proyecciones sintéticas por carecer de masa estadística mínima. Se mostrará un banner color ámbar con la explicación respectiva.

## 4. Simulador Analítico Cyber Days
Para aquellos productos con historial suficiente, en la parte inferior se despliega la tarjeta de impacto logístico de escenarios Cyber Days.
Esta herramienta multiplica el horizonte predictivo base por factores promocionales (**Moderado +20%** e **Intensivo +50%**) y permite cruzar este volumen con la telemetría viva de BigQuery (Stock Disponible Actual).

1. Dar clic en el botón morado **Consultar Inventario Real**.
2. El sistema extraerá de `stock_actual_vw` la cantidad remanente operativa en tiempo real y mostrará los saldos futuros. Si el stock no es suficiente para cubrir los picos, las proyecciones se teñirán de rojo y se emitirá la alerta de quiebre (Out of Stock).

## 5. Exportación Ejecutiva (PDF)
En la esquina superior derecha se encuentra el botón **Generar Informe PDF**.
Éste activará el stylesheet optimizado del navegador, ocultando menús, botoneras de filtro, y fondos oscuros de la web, entregando un reporte técnico a página blanca, con gráficos SVG de alta calidad listos para enviar a *Stakeholders*.
