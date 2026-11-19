# INVENTARIO ANALÍTICO — UCI ONLINE RETAIL

**Fuente:** UCI Online Retail (Transacciones de e-commerce en Reino Unido y Europa)  
**Periodo Histórico:** Diciembre 2010 a Diciembre 2011 (53 semanas).

---

## 1. Naturaleza y Limitaciones de la Fuente
UCI Online Retail provee un log plano de facturación transaccional (InvoiceNo, StockCode, Quantity, UnitPrice). 
A diferencia de sistemas ERP o WMS modernos, **UCI carece de un maestro de inventario físico**. No provee:
- Stock inicial o disponible en almacén.
- Puntos de reorden o lead times de proveedores.
- Registros de merma, traslados o ajustes de inventario no comerciales.

Por lo tanto, la integración de UCI en el módulo de inventarios de LUMINA Retail se ha modelado estrictamente como un **Inventario Analítico de Demanda Histórica**, aislando estos indicadores del inventario operativo real (Olist) para evitar la creación de stock ficticio.

---

## 2. Modelo de Datos Analítico

El modelado ELT en BigQuery (`lumina_sandbox`) consolida tres niveles de granularidad:

### 2.1. Catálogo de Productos (`vw_uci_analytical_product_catalog`)
Vista a nivel de SKU (`source_product_id` / `StockCode`).
- **Métricas:** Unidades vendidas (positivas), Unidades devueltas (negativas), Ingresos brutos GBP, Precio promedio, Meses activos.
- **Clasificación ABC:** Calculada dinámicamente mediante la contribución acumulada a los ingresos históricos (`cum_revenue_pct`). Los productos que concentran el 70% de los ingresos son clase 'A', hasta el 90% clase 'B', y el resto clase 'C'.
- **Demanda Mensual:** `units_sold / active_months`.

### 2.2. Inventario Analítico por País (`vw_uci_analytical_inventory_country`)
Vista a nivel de País y SKU.
- **Propósito:** Identificar la penetración de mercado y los productos más demandados por región (ej. Reino Unido vs. Alemania).
- **Métricas:** Unidades netas, ingresos brutos GBP y conteo de transacciones únicas.

### 2.3. Evolución Mensual (`vw_uci_analytical_inventory_monthly`)
Vista a nivel de Mes (`sales_month`), País y SKU.
- **Propósito:** Analizar la curva de demanda histórica, la estacionalidad intra-anual y los picos de consumo (ej. Q4 2011).

---

## 3. Tratamiento de Devoluciones y Reglas de Calidad
1. **Conservación de `StockCode` y Descripciones:** Se mantiene el código original. Ante variaciones de descripción para un mismo código, se utiliza la última registrada (`MAX(product_name)`).
2. **Cantidades Positivas y Negativas:**
   - Registros con `Quantity > 0` se suman a `units_sold`.
   - Registros con `Quantity < 0` (incluyendo facturas canceladas con prefijo 'C') se suman en valor absoluto a `units_returned`.
   - Las cantidades negativas **no se eliminan** ni se convierten en ventas; se restan aritméticamente en `units_net`.
3. **Moneda:** Todos los cálculos monetarios conservan la divisa nativa **GBP** (Libras Esterlinas).

---

## 4. Endpoints de la API
El backend FastAPI expone los resultados a través de los siguientes endpoints:
- `GET /api/inventory/uci/catalog`: Retorna el top 100 del catálogo analítico clasificado por ingresos.
- `GET /api/inventory/uci/country`: Retorna la penetración del inventario desglosada por país.
- `GET /api/inventory/uci/monthly`: Retorna la agregación mensual histórica de demanda para series de tiempo.

---

## 5. Visualización en el Módulo Inventory
El módulo `Inventory.jsx` (React) despliega una sección inferior exclusiva para UCI con el encabezado: *"Inventario analítico y demanda histórica — UCI Online Retail"*.
- **Indicadores Clave:** Total de productos identificados, Demanda mensual promedio por SKU, Unidades históricas devueltas y Total de mercados activos.
- **Tabla de Catálogo:** Presenta el desglose del top 100 con identificadores visuales (*badges*) de su clase ABC (A en verde, B en amarillo, C en naranja).
- **Gráfica de Tendencia:** Un `LineChart` renderizado con Recharts que muestra la curva de unidades vendidas a lo largo de los 13 meses del dataset.
