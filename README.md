# RetailSmart

Plataforma de analítica comercial y logística multisource.

## Descripción

RetailSmart integra datos de comercio electrónico para analizar ventas, productos, categorías y desempeño logístico.

## Arquitectura

La solución está organizada en los siguientes componentes:

- **Frontend:** React, Vite y Recharts para la visualización de indicadores.
- **Backend:** API REST desarrollada con FastAPI.
- **Almacenamiento analítico:** Google Cloud Storage y BigQuery.
- **Procesamiento:** Apache Spark mediante Dataproc.
- **Streaming:** Apache Kafka y Spark Structured Streaming.
- **Infraestructura:** Google Cloud Platform y Cloud Run.

## Fuentes de datos

El proyecto integra dos fuentes de comercio electrónico:

- **Olist:** datos de comercio electrónico brasileño. Moneda: BRL.
- **TheLook:** datos de comercio electrónico. Moneda: USD.

Los indicadores monetarios se presentan por separado, respetando la moneda de origen de cada fuente. No se suman ni comparan directamente valores expresados en monedas diferentes.

## Funcionalidades

El dashboard incluye los siguientes módulos:

- **Overview:** visión general de los indicadores comerciales y logísticos.
- **Commercial:** análisis de ventas, evolución mensual, categorías y productos.
- **Logistics:** indicadores de envíos, entregas, cobertura y calidad logística.
- **Sources:** información sobre las fuentes de datos utilizadas.

## API REST

La API expone los siguientes endpoints:

- `/api/health`: estado del servicio.
- `/api/commercial/summary`: resumen comercial.
- `/api/commercial/monthly`: evolución mensual.
- `/api/commercial/categories`: desempeño por categoría.
- `/api/commercial/products`: desempeño por producto.
- `/api/logistics/summary`: resumen logístico.
- `/api/logistics/monthly`: evolución logística mensual.

## Ejecución local

### Backend

Desde la raíz del proyecto:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

La configuración de acceso a Google Cloud debe realizarse mediante variables de entorno y credenciales autorizadas. No se deben publicar credenciales ni secretos en el repositorio.

## Procesamiento en streaming

El proyecto incorpora un flujo de procesamiento de eventos en tiempo real:

1. Apache Kafka recibe los eventos de telemetría.
2. Spark Structured Streaming procesa los mensajes.
3. Los resultados se almacenan en Google Cloud Storage.
4. Los datos procesados pueden consultarse para auditoría y análisis.

El flujo utiliza checkpoints para conservar el progreso del procesamiento y facilitar la recuperación ante interrupciones.

## Consideraciones analíticas

- Los resultados de Olist y TheLook se analizan respetando sus respectivas monedas y poblaciones de datos.
- Los indicadores comerciales y logísticos utilizan universos de datos y criterios de cálculo distintos.
- Los periodos mensuales pueden incluir meses parciales, por lo que deben interpretarse considerando su cobertura temporal.
- Los indicadores no disponibles se representan como valores nulos y no como cero.
