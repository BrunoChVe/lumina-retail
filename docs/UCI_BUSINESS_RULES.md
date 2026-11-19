# Reglas de Negocio: UCI Online Retail

## 1. Tratamiento de Importes y Moneda
- **Aislamiento de Divisa:** UCI mantiene en todos sus agregados la moneda de origen (`GBP`). No se consolida en una misma tarjeta KPIs de GBP, USD (TheLook) y BRL (Olist) debido al sesgo de tipo de cambio y ausencia de snapshots FX históricos.
- **Venta Bruta (`gross_sales`):** Sumatoria exclusiva de registros donde `Quantity > 0` multiplicada por `UnitPrice`.

## 2. Cancelaciones y Devoluciones
- **Patrón 'C':** Si `InvoiceNo` (ahora `source_order_id`) inicia con 'C', la transacción se clasifica explícitamente como cancelación.
- **Ajustes Negativos:** Todo registro donde `Quantity < 0` (incluya o no la 'C' en el ID) se cuantifica como `return_sales` o ajuste negativo, deduciéndose de las ventas brutas para obtener el `net_sales` en vistas agregadas.

## 3. Manejo de Identidad
- **Clientes Huérfanos:** Los registros con `CustomerID` nulo representan más del 24% del volumen transaccional de UCI. En lugar de descartarse (para evitar destrucción de valor monetario documentado), se conservan bajo un ID sintético `ANONYMOUS` pero no se incluyen en el conteo de `Clientes Identificados`.

## 4. Derivación de Taxonomías
Al no contar con una tabla dimensional de Categorías y Subcategorías, se emplearon reglas `REGEX` en el nivel Silver sobre la columna `Description`.
- Se agruparon en siete (7) categorías base, como "Kitchen & Dining" o "Home Decor & Lighting".
- Los registros inyectados con descripciones no estandarizadas o comisiones se etiquetan como "Unclassified". El linaje se rastrea bajo la etiqueta `DERIVED_RULE` o `UNCLASSIFIED`.
