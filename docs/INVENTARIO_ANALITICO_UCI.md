# INVENTARIO ANALÍTICO — UCI ONLINE RETAIL

**Fuente:** UCI Online Retail (Transacciones de e-commerce en Reino Unido y Europa)  
**Periodo Histórico:** Diciembre 2010 a Diciembre 2011 (53 semanas).  
**Moneda Original:** GBP (£ - Libra Esterlina).

---

## 1. Naturaleza y Limitaciones de la Fuente
UCI Online Retail provee un log transaccional de facturación (InvoiceNo, StockCode, Quantity, UnitPrice, InvoiceDate, CustomerID, Country). 
A diferencia de sistemas ERP o WMS modernos, **UCI carece de un maestro de inventario físico**. No provee:
- Stock inicial o disponible en almacén.
- Puntos de reorden o lead times de proveedores.
- Registros de merma, traslados o ajustes de inventario no comerciales.
- Identificador de tienda física o sucursal.

Por lo tanto, la integración de UCI en el módulo de inventarios de LUMINA Retail se ha modelado estrictamente como un **Inventario Analítico de Demanda Histórica**, aislando estos indicadores del inventario operativo real (Olist) para evitar la creación de stock ficticio.

---

## 2. Modelo de Datos Analítico

El modelado ELT en BigQuery (`lumina_sandbox`) consolida tres niveles de granularidad:

### 2.1. Catálogo de Productos (`vw_uci_analytical_product_catalog`)
Vista a nivel de SKU (`source_product_id` / `StockCode`).
- **Métricas:** Unidades vendidas (positivas), Unidades devueltas (negativas), Unidades netas, Ingresos brutos GBP, Precio promedio, Meses activos.
- **Clasificación ABC:** Calculada dinámicamente mediante la contribución acumulada a los ingresos históricos (`cum_revenue_pct`). Los productos que concentran el 70% de los ingresos son clase 'A' (524 SKUs), hasta el 90% clase 'B' (789 SKUs), y el resto clase 'C' (2,628 SKUs).
- **Demanda Mensual Promedio:** `units_sold / active_months`.

### 2.2. Inventario Analítico por País (`vw_uci_analytical_inventory_country`)
Vista a nivel de País y SKU.
- **Propósito:** Identificar la penetración de mercado y los productos más demandados por mercado geográfico (ej. Reino Unido vs. Alemania vs. Francia).
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

## 4. Endpoints de la API y Filtros Disponibles
El backend FastAPI expone los resultados a través de los siguientes endpoints parametrizados:
- `GET /api/inventory/metadata`: Retorna listas para filtros dependientes (regiones operativas, productos operativos, países UCI, clases ABC).
- `GET /api/inventory/uci/summary`: Retorna KPIs principales y distribución ABC con soporte para filtros `country`, `stock_code` y `abc_class`.
- `GET /api/inventory/uci/catalog`: Retorna catálogo analítico con soporte para filtros `limit`, `stock_code`, `abc_class` y `country`.
- `GET /api/inventory/uci/country`: Retorna la penetración del inventario por país con filtros opcionales `country` y `stock_code`.
- `GET /api/inventory/uci/monthly`: Retorna la agregación mensual histórica de demanda con filtros opcionales `country` y `stock_code`.

---

## 5. Visualización en el Módulo Inventory
El módulo `Inventory.jsx` (React) despliega la sección destacada:
**ANÁLISIS DE INVENTARIO Y DEMANDA HISTÓRICA — UCI ONLINE RETAIL**

- **Barra de Filtros Combinables:** Permite segmentar simultáneamente por Fuente (`ALL`, `operational`, `uci`), País (`38 países`), Código de Producto y Clase ABC (`A`, `B`, `C`).
- **Indicadores Principales:** 6 tarjetas KPI (Total de Productos, Unidades Comercializadas, Unidades Devueltas, Ingresos GBP, Países Comerciales y Periodo Histórico).
- **Gráfico 1 — Evolución Mensual:** BarChart interactivo con selector de series (Todas las series, Unidades vendidas, Devoluciones, Demanda neta).
- **Gráfico 2 — Top 10 Productos con Mayor Demanda:** BarChart horizontal con código SKU, descripción y ventas en GBP.
- **Gráfico 3 — Clasificación ABC:** BarChart y tarjetas de resumen que reflejan la distribución del catálogo (Clase A: 524 SKUs / 70% ventas, Clase B: 789 SKUs / 20%, Clase C: 2,628 SKUs / 10%).
- **Gráfico 4 — Demanda por País:** Top 10 mercados internacionales ordenados por volumen comercializado.
- **Tabla de Catálogo Analítico:** Buscador en tiempo real por texto, badges visuales por clase ABC, unidades vendidas, devoluciones, demanda promedio mensual y formateo en moneda GBP.
