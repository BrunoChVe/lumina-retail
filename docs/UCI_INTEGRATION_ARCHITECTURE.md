# Arquitectura de Integración: UCI Online Retail

## 1. Visión General
UCI Online Retail se integra a LUMINA Retail como la tercera fuente transaccional, expandiendo la cobertura de la plataforma hacia operaciones B2B/B2C en el Reino Unido y Europa (2010-2011). Al carecer de un modelo dimensional robusto, su integración depende de un procesamiento ELT intensivo en BigQuery bajo el estándar WAP.

## 2. Pipeline ELT
1. **Bronze (`stg_uci_online_retail`)**: Ingesta bruta y validación de tipos básicos.
2. **Silver (`vw_commercial_category_performance_v1`)**: Aplicación de reglas de limpieza, filtrado de cancelaciones (`quantity < 0`), y derivación de categorías mediante expresiones regulares sobre descripciones de texto libre.
3. **Gold (`gold_commercial_monthly`, `gold_commercial_categories`, etc.)**: Agregación analítica por dimensiones temporales y de producto, aislando estrictamente la moneda original (GBP).

## 3. Gobernanza y WAP-02.1
- **Write**: Materialización en un esquema auditado (`lumina_sandbox`).
- **Audit**: Verificación de nulos en `source_order_id`, integridad de llaves cruzadas y no negatividad en ventas brutas.
- **Publish**: Confirmación de la transacción y exposición en vistas consumibles para el backend FastAPI.

## 4. Limitaciones Estructurales
- **Sin Taxonomía**: Clasificación dependiente del texto `Description`.
- **Ausencia de Tiempos Logísticos**: Inviabilidad para calcular SLAs o `late_delivery_rate`.
- **Falta de Inventario**: El campo `Quantity` es transaccional y no representa un snapshot de stock en almacén.
