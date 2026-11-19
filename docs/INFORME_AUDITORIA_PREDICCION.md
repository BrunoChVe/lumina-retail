# INFORME DE AUDITORÍA Y RECUPERACIÓN DEL MÓDULO PREDICCIÓN DE DEMANDA

## 1. Falla Inicial Reportada
El módulo `Predictive` dejó de cargar en producción tras la ampliación de filtros por tienda, vendedor, país y producto implementada en la iteración previa. El frontend no renderizaba correctamente los componentes y el contenedor de FastAPI en Google Cloud Run fallaba durante el arranque.

## 2. Causa Raíz Diagnosticada

### 2.1. Backend (FastAPI / Cloud Run)
El contenedor Docker de Cloud Run (`lumina-retail-00015-7w2`) abortaba su inicio con el error crítico:
```
ModuleNotFoundError: No module named 'backend'
```
* **Diagnóstico:** Al introducir el nuevo script `backend/app/forecasting.py` para calcular modelos estadísticos granulares sobre la marcha, se introdujo la librería `numpy`. Sin embargo, `numpy` no fue declarado en el `requirements.txt`. Como resultado, la instrucción `import numpy` lanzaba un `ModuleNotFoundError`. El bloque `try/except` en `main.py` capturaba el error y, al intentar el fallback de ruta absoluta `from backend.app.forecasting`, volvía a fallar porque dentro del contenedor el directorio de trabajo es `/app`.

### 2.2. Frontend (React)
El componente `Predictive.jsx` fue reestructurado para utilizar filtros dependientes. Sin embargo, al consultar combinaciones de dimensiones con "historial insuficiente" (ej. vendedor de Olist con un producto recién listado), la API retornaba un objeto JSON que omitía los campos de tendencias (ej. `forecastResult.metrics`). La UI original intentaba desestructurar ciegamente estos parámetros anidados para el gráfico, provocando un error en el motor de renderizado de React.

## 3. Correcciones Aplicadas

1. **Gestión de Dependencias:** Se agregó `numpy` al archivo `requirements.txt`.
2. **Refactorización de Rutas de Importación:** Se ajustaron los bloques `try/except` en `main.py` para priorizar las rutas de paquete absoluto (`backend.app...`) seguidas de las relativas, y se configuró para que no silenciara excepciones subyacentes de dependencias.
3. **Manejo Defensivo en React:** Se refactorizó `Predictive.jsx` utilizando renders condicionales explícitos. Si `forecastResult?.sufficient_history` es `false`, la UI ahora aborta el renderizado de gráficos y métricas estocásticas, presentando en su lugar un banner de advertencia ("Historial Insuficiente para Pronóstico Estadístico Confiable").
4. **Validación WAP Intacta:** El error no comprometió las tablas analíticas. El modelo Gold original en BigQuery se conservó íntegro y las métricas de evaluación del modelo por Categoría no se perdieron.

## 4. Evidencias y Pruebas
Tras las correcciones, se ejecutó la suite de integración completa.
- **Entorno Local:** `pytest backend/tests` -> 75 PASSED (100% éxito).
- **Despliegue:** Se generó la imagen multi-etapa y Cloud Run levantó saludablemente (Health Check `ContainerHealthy: True` en 4.5s).
- El sistema de predicción granular ahora opera sin caídas bajo todas las combinaciones dimensionales válidas e inválidas.