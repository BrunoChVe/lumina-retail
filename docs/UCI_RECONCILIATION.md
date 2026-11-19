# Reconciliación Analítica: UCI Online Retail

El proceso de reconciliación busca demostrar matemáticamente que la capa Gold WAP de LUMINA mantiene total fidelidad con la fuente de datos plana de UCI (`stg_uci_online_retail`).

## 1. Volumen Físico de Registros
- **Consulta Bronze:** `SELECT COUNT(*) FROM stg_uci_online_retail`
- **Volumen Esperado:** 541,909
- **Filas Gold procesadas:** 541,909 (100% Retención en `vw_commercial_product_performance_v1`).

## 2. Ventas Brutas Totales (Gross Sales)
Regla: Sumatoria de `Quantity * UnitPrice` exclusiva de `Quantity > 0`.
- **Resultado Bronze:** ~£10.64 Millones (10,642,110.8 GBP aprox).
- **Métrica Gold WAP:** Coincidencia exacta validada en `vw_commercial_countries`.

## 3. Ajustes y Devoluciones (Return Sales)
Regla: Sumatoria de valor absoluto de `Quantity * UnitPrice` exclusiva de `Quantity < 0`.
- **Resultado Bronze:** ~£896,812.49 GBP.
- **Métrica Gold WAP:** Coincidencia exacta validada en la vista `vw_commercial_cancellations` como `return_sales`.

## 4. Identificación de Países
- **Únicos Bronze:** 38 Países.
- **Top 3 Bronze:** Reino Unido, Alemania, Francia.
- **Resultados Gold WAP:** Se listan 38 registros provenientes de `uci` en `vw_commercial_countries`, reteniendo a Reino Unido como el puntero del mercado europeo con el ~85% del volumen general de ventas.
