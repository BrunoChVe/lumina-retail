import os
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

PROJECT_ID = (
    os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("GCP_PROJECT", "lumina-retail-001")
)
DATASET = os.getenv("BQ_DATASET") or os.getenv("DATASET", "lumina_stage")
STREAMING_DATASET = os.getenv("STREAMING_DATASET", "lumina_streaming")

client = bigquery.Client(project=PROJECT_ID)

app = FastAPI(
    title="Lumina Retail API",
    description="API de inteligencia comercial y logística",
    version="1.0.0"
)

origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://localhost:8080,http://127.0.0.1:5173,http://127.0.0.1:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def execute_query(sql):
    try:
        rows = client.query(sql).result()
        output = []

        for row in rows:
            item = {}
            for key, value in dict(row).items():
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()
                elif isinstance(value, Decimal):
                    value = float(value)
                item[key] = value
            output.append(item)

        return output

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "project": PROJECT_ID,
        "dataset": DATASET,
        "streaming_dataset": STREAMING_DATASET,
        "frontend_mounted": FRONTEND_DIST.exists()
    }


@app.get("/api/commercial/summary")
def commercial_summary():
    return execute_query(f"""
        SELECT
            source_system,
            source_label,
            currency_code,
            currency_status,
            SUM(total_orders) AS total_orders,
            SUM(total_items) AS total_items,
            SUM(total_product_sales) AS total_product_sales,
            SUM(completed_orders) AS completed_orders,
            SUM(completed_product_sales) AS completed_product_sales
        FROM `{PROJECT_ID}.{DATASET}.vw_commercial_dashboard_final_v1`
        GROUP BY 1, 2, 3, 4
        ORDER BY source_system
    """)


@app.get("/api/commercial/monthly")
def commercial_monthly():
    return execute_query(f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET}.vw_commercial_monthly_final_v1`
        ORDER BY order_month, source_system
    """)


@app.get("/api/commercial/categories")
def commercial_categories():
    return execute_query(f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET}.vw_commercial_category_performance_v1`
        WHERE category_rank <= 15
        ORDER BY source_system, category_rank
    """)


@app.get("/api/commercial/products")
def commercial_products():
    return execute_query(f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET}.vw_commercial_product_performance_v1`
        WHERE sales_rank <= 20
        ORDER BY source_system, sales_rank
    """)


@app.get("/api/logistics/summary")
def logistics_summary():
    return execute_query(f"""
        SELECT
            source_system,
            source_label,
            SUM(total_orders) AS total_orders,
            SUM(valid_shipments) AS valid_shipments,
            SUM(valid_deliveries) AS valid_deliveries,
            SAFE_MULTIPLY(
                SAFE_DIVIDE(SUM(valid_shipments), SUM(total_orders)),
                100
            ) AS shipment_coverage_pct,
            SAFE_MULTIPLY(
                SAFE_DIVIDE(SUM(valid_deliveries), SUM(total_orders)),
                100
            ) AS delivery_coverage_pct,
            SUM(deliveries_with_estimate) AS deliveries_with_estimate,
            SUM(late_deliveries) AS late_deliveries,
            SUM(valid_returns) AS valid_returns,
            SUM(invalid_shipping_sequence) AS invalid_shipping_sequence,
            SUM(invalid_delivery_sequence) AS invalid_delivery_sequence,
            SUM(delivery_without_shipment) AS delivery_without_shipment,
            SUM(future_shipments) AS future_shipments,
            SUM(future_deliveries) AS future_deliveries,
            CASE
                WHEN COUNTIF(late_delivery_data_status = 'available') > 0
                THEN SAFE_DIVIDE(
                    SUM(late_deliveries),
                    SUM(deliveries_with_estimate)
                ) * 100
                ELSE NULL
            END AS late_delivery_rate_pct,
            CASE
                WHEN COUNTIF(late_delivery_data_status = 'available') > 0
                THEN 'available'
                ELSE 'not_available'
            END AS late_delivery_data_status
        FROM `{PROJECT_ID}.{DATASET}.vw_logistics_dashboard_final_v1`
        GROUP BY source_system, source_label
        ORDER BY source_system
    """)


@app.get("/api/logistics/monthly")
def logistics_monthly():
    return execute_query(f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET}.vw_logistics_dashboard_final_v1`
        ORDER BY order_cohort_month, source_system
    """)



@app.get("/api/inventory/current")
def inventory_current():
    return execute_query(f"""
        SELECT
            product_id,
            region,
            stock_registrado,
            fecha_ultimo_evento,
            fecha_procesamiento,
            minutos_desde_evento,
            estado_frescura,
            CASE
                WHEN stock_registrado < 10 THEN 'CRITICO'
                WHEN stock_registrado <= 20 THEN 'BAJO'
                ELSE 'NORMAL'
            END AS estado_stock
        FROM `{PROJECT_ID}.{STREAMING_DATASET}.stock_actual_vw`
        WHERE (region IS NULL OR region != 'CYBER_TEST')
        ORDER BY stock_registrado ASC, product_id, region
    """)


@app.get("/api/inventory/risks")
def inventory_risks():
    return execute_query(f"""
        SELECT
            product_id,
            region,
            total_eventos,
            stock_promedio,
            stock_minimo,
            stock_maximo,
            alertas_criticas,
            eventos_stock_bajo,
            porcentaje_alertas
        FROM `{PROJECT_ID}.{STREAMING_DATASET}.stock_risk_by_product_region`
        WHERE (region IS NULL OR region != 'CYBER_TEST')
        ORDER BY alertas_criticas DESC, stock_minimo ASC
    """)



@app.get("/api/predictive/metrics")
def predictive_metrics():
    return execute_query(f"""
        SELECT
            run_id,
            model_name,
            metric,
            value,
            target,
            split_start,
            split_end,
            n_test_rows,
            evaluated_at,
            evaluation_type
        FROM `{PROJECT_ID}.{DATASET}.model_evaluation_metrics`
        WHERE run_id = (
            SELECT run_id
            FROM `{PROJECT_ID}.{DATASET}.model_evaluation_metrics`
            ORDER BY evaluated_at DESC
            LIMIT 1
        )
        ORDER BY metric
    """)


@app.get("/api/predictive/predictions")
def predictive_predictions():
    return execute_query(f"""
        SELECT
            semana,
            categoria,
            actual,
            prediccion,
            error_absoluto
        FROM `{PROJECT_ID}.{DATASET}.model_evaluation_predictions`
        WHERE run_id = (
            SELECT run_id
            FROM `{PROJECT_ID}.{DATASET}.model_evaluation_metrics`
            ORDER BY evaluated_at DESC
            LIMIT 1
        )
        ORDER BY semana, categoria
    """)


# Frontend React compilado con Vite (Docker: /app/frontend/dist; Local: ../frontend/dist)
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if not FRONTEND_DIST.exists():
    FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIST, html=True),
        name="frontend"
    )
