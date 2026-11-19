# INFORME FINAL DE CERTIFICACIÓN TÉCNICA
**LUMINA Retail — Intelligence & Operations Platform**
**Fecha de Certificación:** 19 de Noviembre de 2026
**Responsable Técnico:** LUMINA Cloud Data Engineering Team

---

## 1. Resumen Ejecutivo
El proyecto LUMINA Retail se ha completado y validado en su totalidad. Se integraron con éxito las tres fuentes de datos solicitadas (Olist, TheLook y UCI Online Retail), aislando estructuralmente sus dominios monetarios y reglas de negocio. La plataforma expone un backend FastAPI de alto rendimiento (17 endpoints validados) y un dashboard interactivo moderno (React 19 / Vite). 

Se desplegaron componentes de infraestructura Big Data, integrando una arquitectura Medallion (ELT en BigQuery) y un motor de streaming robusto (Apache Spark y Apache Kafka) para la telemetría de inventarios. Todos los módulos analíticos operan protegidos mediante un protocolo propio de gobernanza transaccional de lectura (WAP-02.1).

El crédito de infraestructura en la nube fue protegido al pausar preventivamente los clústeres de cómputo inactivos. El entorno se encuentra estable, documentado y listo para su presentación académica.

---

## 2. Arquitectura Final y Componentes
1. **Frontend:** Single Page Application construida con React 19 y Vite. Gráficas de alta densidad vía Recharts.
2. **Backend API:** FastAPI (Python 3.12) con manejo asíncrono y control de excepciones.
3. **Data Lake / DWH:** Google Cloud Storage y BigQuery como almacenamiento analítico serverless.
4. **Data Engineering (Batch):** ELT implementado íntegramente en SQL sobre BigQuery, gobernado por protocolo WAP (Write-Audit-Publish) optimista.
5. **Data Engineering (Streaming):** Producción en Apache Kafka y procesamiento en micro-lotes de 5s mediante Dataproc (Spark Structured Streaming).
6. **Machine Learning:** Modelo supervisado de demanda estacional (XGBoost) y línea base ($t-1$) evaluados a través de `scikit-learn`.
7. **Despliegue:** Imagen multi-etapa ejecutada bajo Google Cloud Run con seguridad perimetral Identity-Aware Proxy (IAP).

---

## 3. Matriz de Componentes y Estado de Validación

| Componente | Implementado | Validado | Evidencia | Estado |
|---|---|---|---|---|
| **Integración Olist (BRL)** | Sí | Sí | Endpoints comerciales, tablas `fact_sales_multisource`. Pruebas OK. | **COMPLETADO Y VALIDADO** |
| **Integración TheLook (USD)** | Sí | Sí | UI comercial multi-moneda. | **COMPLETADO Y VALIDADO** |
| **Integración UCI (GBP)** | Sí | Sí | Extracción mediante REGEX para taxonomías; segregación monetaria. | **COMPLETADO Y VALIDADO** |
| **Gobernanza WAP** | Sí | Sí | 4 dominios en `gold_release_control` con status `PUBLISHED`. | **COMPLETADO Y VALIDADO** |
| **Backend & API** | Sí | Sí | 17 endpoints HTTP con tests (100% aprobados). | **COMPLETADO Y VALIDADO** |
| **Frontend & Dashboard** | Sí | Sí | Vite build en `< 2s`, despliegue SPA sin gráficos vacíos. | **COMPLETADO Y VALIDADO** |
| **Streaming Kafka/Spark** | Sí | Sí | Trazabilidad Kafka (offset 2901) a BigQuery (`telemetria_consolidada`). | **COMPLETADO Y VALIDADO** |
| **Simulación Cyber Days** | Sí | Sí | 795 eventos procesados, segregados visual y físicamente. | **COMPLETADO Y VALIDADO** |
| **Machine Learning (XGBoost)** | Sí | Sí | Backtest de 888 semanas, Benchmark $t-1$ WAPE 35.49%. | **COMPLETADO Y VALIDADO** |
| **Cloud Run (Despliegue)** | Sí | Sí | `lumina-retail-00009-5hg` operando con el 100% del tráfico. | **COMPLETADO Y VALIDADO** |

---

## 4. Gobernanza y Calidad de Datos (Pipelines WAP)
Todos los dominios analíticos Gold superaron exitosamente las 16 auditorías automatizadas (nulos, unicidad, integridad referencial y temporal) previas a su paso a producción.
- **Commercial:** `run_commercial_20261119085528_c222ee`
- **Logistics:** `run_logistics_20261119061637_0af4ef`
- **Inventory:** `run_inventory_20261119073856_f3a377`
- **Predictive:** `run_predictive_20261119083122_8b5685`

---

## 5. Simulación Cyber Days y Evidencias Streaming
- **Ejecución (Run ID):** `87cc5b11-926d-4525-a42e-feeab5ff6f99`
- **Evidencias GCS:** 28 archivos Parquet bajo la carpeta de checkpoints (commits 20-26).
- **Evidencias BigQuery:** Exactamente 795 eventos registrados (`SYNTHETIC_CYBERDAY_STRESS`) sin contaminación alguna en el historial comercial (`fact_sales_multisource`).
- **Rendimiento Comprobado:** Emisión a 24.8 eventos/s, capacidad pico de ingesta Spark a 49.6 eventos/s. Retraso (lag) inferior a un micro-lote (< 5s).
- Se implementó exitosamente el aislamiento del endpoint `GET /api/inventory/current` con soporte dinámico para habilitar/deshabilitar los registros sintéticos de forma parametrizada.

---

## 6. Recursos Activos, Pausados y Gestión de Costos

### Instancias de Cómputo Pausadas (Ahorro Significativo de Créditos)
Se detuvieron preventivamente los recursos para evitar sangrado innecesario de créditos durante la inactividad:
- **Máquina Virtual Kafka (`lumina-kafka-vm`):** Estado **TERMINATED** (Zona: `us-east1-b`).
- **Clúster Dataproc (`lumina-retail-spark`):** Estado **TERMINATED** (3 VMs `e2-standard-4`, 12 vCPUs).
- *El job PySpark de streaming se detuvo de manera controlada para permitir reanudación de checkpoints.*

### Recursos Residuales Activos (Costos Mínimos de Retención)
La plataforma preserva persistencia histórica para habilitar la reactivación instantánea del servicio web y de los datos analíticos:
- **Cloud Run:** Escala dinámica. Sin costo durante 0 instancias o uso de Free Tier.
- **BigQuery:** Costos nominales por almacenamiento de tablas y procesamiento durante lecturas analíticas activadas por la API.
- **Google Cloud Storage (GCS):** Costo operativo nominal para conservación del Data Lake, Parquets y Checkpoints.
- **Discos Persistentes (GCE):** Retención pasiva del estado de las VMs Dataproc y Kafka para reinicios futuros (Costos por GB aprovisionado inactivo).
- **Artifact Registry:** Repositorios de Docker almacenando 280MB de capas.

---

## 7. Limitaciones y Alcance Restringido
1. **Ausencia de SLA Logístico en UCI Online Retail:** A diferencia de Olist o TheLook, UCI es una fuente meramente transaccional. Para prevenir falsificación métrica, se excluye de las visualizaciones y cálculos del módulo Logístico.
2. **Inviabilidad Predictiva sobre UCI:** XGBoost y métodos estacionales como Seasonal Naive requieren ventanas mínimas de aprendizaje multi-anual para prevenir sobreajuste. Al disponer de tan solo 53 semanas de datos, el cálculo predictivo se restringe formalmente a Olist.
3. **Mapeo Dimensional de Tiendas:** Como no existen atributos de "tiendas físicas unificadas" multi-fuente, la dimensión del Store Performance Dashboard segmenta el desempeño utilizando el Data Source y la Región comercial nativa para permitir visualización consolidada de negocios (Marketplace vs. Global vs. Retail UK).

---

## 8. Procedimiento de Demostración Académica
La plataforma ya está certificada, pre-compilada y su frontend expuesto en Cloud Run con protección nativa.
Para interactuar con la aplicación:
1. Asegurar credenciales OIDC de acceso para el servicio Cloud Run protegido vía Identity-Aware Proxy (IAP).
2. Ingresar a la URL Productiva: `https://lumina-retail-sv5avv2ypq-uc.a.run.app`.
3. Navegar en el menú lateral para atestiguar la integridad, limpieza visual, y separación de monedas de los componentes.
4. Ingresar al **Módulo Inventario** e interactuar con el interruptor de visualización **"Simulación Cyber Days"**. Se comprobará en vivo la expansión de la data real al incluir a los identificadores del clúster de prueba (`CYBER_TEST`, badge "SINTÉTICO").

**Commit Final Registrado:** ` origin/main ` (Sincronización Total Verificada).