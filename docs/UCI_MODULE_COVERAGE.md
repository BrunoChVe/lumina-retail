# Cobertura de Módulos: UCI Online Retail

| Módulo LUMINA | Estado de Integración | Observaciones y Limitaciones |
| :--- | :--- | :--- |
| **Resumen Ejecutivo (Overview)** | COMPLETADO | Se integran los volúmenes transaccionales y la gráfica histórica aislando la divisa a `GBP`. |
| **Store Performance** | COMPLETADO | Agregado exitosamente. Se documenta la limitación explícita de carecer de una división en múltiples tiendas físicas reales. |
| **Análisis Comercial** | COMPLETADO | Incorporación de las reglas REGEX para categorización. Las tarjetas diferencian divisas nativas y el ranking incluye productos de UCI. |
| **Análisis Logístico** | COMPLETADO CON LIMITACIÓN DE FUENTE | UCI carece de marcas de tiempo logísticas (fechas de despacho, entrega). Se indica explícitamente en la UI que la fuente no aporta datos para `late_delivery_rate` ni SLAs. |
| **System Health & Data Sources** | COMPLETADO | Dashboard de salud auditado muestra métricas de retención de clientes válidos frente a `ANONYMOUS` y volúmenes monetarios. |
| **Control de Inventario** | NO APLICABLE | El módulo evalúa eventos de streaming de bodegas logísticas modernas de Brasil; UCI posee únicamente `Quantity` transaccional que documenta unidades despachadas, no niveles de stock operativo. |
| **Predicción de Demanda** | BLOQUEADO (LIMITACIÓN METODOLÓGICA) | Explicado en el reporte de viabilidad: 53 semanas impiden configurar correctamente métricas de estacionalidad robusta y Backtest ML sin fuga de datos o severo riesgo de overfit. |
