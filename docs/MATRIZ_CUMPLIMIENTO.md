# Matriz de Cumplimiento: LUMINA Retail

| Requisito / Hito | Resultado | Evidencia |
|---|---|---|
| **1. Auditoría del modelo y Tiendas** | Completado | `vw_store_dimension` y `docs/INFORME_PREDICTIVO_Y_UI.md` mapean lógicamente las fuentes ante la falta de tiendas físicas reales. |
| **2. Integración de UCI Online Retail** | Completado | Presente en vistas analíticas (Commercial, Overview) con cálculo de devoluciones basado en quantity negativa. Aislamiento estricto de moneda GBP. |
| **3. Implementación de Vistas SQL** | Completado | Creadas `vw_store_commercial_performance`, `vw_store_logistics_performance`, `vw_predictive_category_performance` y `vw_store_dimension` en `lumina_sandbox`. |
| **4. Modelo Predictivo Mejorado** | Completado | Evaluado LightGBM vs XGBoost vs Naive(t-1). WAPE mejorado de 36.60% a 36.34% publicado atómicamente en WAP Gold. |
| **5. Rediseño UX/UI Premium SaaS** | Completado | SPA en React reestructurada a tema oscuro corporativo (`#0b1120`). Nuevos componentes integrados (`StorePerf.jsx`). |
| **6. APIs y Contratos de Datos** | Completado | Endpoints extendidos (e.g. `/api/store/performance`). Control HTTP 503 ante falta de *release*. |
| **7. Suite de Pruebas (Calidad)** | Completado | 52 / 52 pruebas exitosas en `unittest` local, incluyendo aceptación del protocolo WAP-02.1. |
| **8. Configuración de Automatización** | Completado | Configurado `config/gemini_allowlist.md` indicando permisos requeridos y reglas de IAM restrictivas para la CLI. |
| **9. Documentación y Entregables** | Completado | Creados `INFORME_ARQUITECTURA_Y_GOBERNANZA_WAP.md`, `INFORME_PREDICTIVO_Y_UI.md`, y el propio `README.md`. |
| **10. Construcción y Despliegue** | Completado | Revisión `wap-gold-final-v2` (`lumina-retail-00009-bub`) desplegada exitosamente en Cloud Run con 100% de tráfico. |
| **11. Control de Versiones GitHub** | Completado | Commits subidos a `origin/main` de forma limpia y transparente. Hash final: `22d0b44`. |

---
**URL de Producción Activa:** [https://lumina-retail-sv5avv2ypq-uc.a.run.app](https://lumina-retail-sv5avv2ypq-uc.a.run.app) *(Protegida por IAM / Identity-Aware Proxy)*  
**Tráfico Asignado:** 100% a `lumina-retail-00009-bub`.
