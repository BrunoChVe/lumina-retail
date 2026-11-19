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
WAP_DATASET = os.getenv("WAP_DATASET", "lumina_sandbox")

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


def execute_query(sql, domain_check=None):
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

        if domain_check and len(output) == 0:
            check_sql = f"""
                SELECT current_run_id, status
                FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
                WHERE domain = '{domain_check}'
            """
            chk = list(client.query(check_sql).result())
            if not chk or chk[0]["status"] != "PUBLISHED" or not chk[0]["current_run_id"]:
                raise HTTPException(
                    status_code=503,
                    detail=f"No existe una versión publicada válida para el dominio '{domain_check}' en {WAP_DATASET}."
                )

        return output

    except HTTPException:
        raise
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
            CASE source_system
                WHEN 'olist' THEN 'documented'
                WHEN 'thelook' THEN 'user_confirmed'
                WHEN 'uci' THEN 'documented'
                ELSE 'unverified'
            END AS currency_status,
            SUM(total_orders) AS total_orders,
            SUM(total_items) AS total_items,
            ROUND(SUM(total_product_sales), 2) AS total_product_sales,
            SUM(completed_orders) AS completed_orders,
            ROUND(SUM(completed_product_sales), 2) AS completed_product_sales
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_commercial_monthly`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'commercial' AND status = 'PUBLISHED'
        )
        GROUP BY 1, 2, 3, 4
        ORDER BY source_system
    """, domain_check="commercial")


@app.get("/api/commercial/monthly")
def commercial_monthly():
    return execute_query(f"""
        SELECT
            source_system,
            source_label,
            currency_code,
            order_month,
            total_orders,
            total_items,
            total_product_sales,
            completed_orders,
            completed_items,
            completed_product_sales,
            avg_completed_order_value,
            completed_order_rate_pct,
            completed_sales_share_pct
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_commercial_monthly`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'commercial' AND status = 'PUBLISHED'
        )
        ORDER BY order_month, source_system
    """, domain_check="commercial")


@app.get("/api/commercial/categories")
def commercial_categories():
    return execute_query(f"""
        SELECT
            source_system,
            currency_code,
            category,
            category_rank,
            items_sold,
            distinct_products,
            orders,
            total_sales,
            avg_item_price,
            sales_share_pct
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_commercial_categories`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'commercial' AND status = 'PUBLISHED'
        )
        AND category_rank <= 15
        ORDER BY source_system, category_rank
    """, domain_check="commercial")


@app.get("/api/commercial/products")
def commercial_products():
    return execute_query(f"""
        SELECT
            source_system,
            source_product_id,
            product_name,
            category,
            brand,
            department,
            items_sold,
            orders,
            total_sales,
            avg_item_price,
            currency_code,
            sales_rank
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_commercial_products`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'commercial' AND status = 'PUBLISHED'
        )
        AND sales_rank <= 20
        ORDER BY source_system, sales_rank
    """, domain_check="commercial")


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
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_logistics_dashboard`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'logistics' AND status = 'PUBLISHED'
        )
        GROUP BY source_system, source_label
        ORDER BY source_system
    """, domain_check="logistics")


@app.get("/api/logistics/monthly")
def logistics_monthly():
    return execute_query(f"""
        SELECT
            source_system,
            order_cohort_month,
            source_label,
            total_orders,
            valid_shipments,
            valid_deliveries,
            deliveries_with_estimate,
            late_deliveries,
            valid_returns,
            invalid_shipping_sequence,
            invalid_delivery_sequence,
            delivery_without_shipment,
            future_shipments,
            future_deliveries,
            future_returns,
            avg_shipping_hours,
            avg_delivery_hours,
            shipment_coverage_pct,
            delivery_coverage_pct,
            late_delivery_rate_pct,
            late_delivery_data_status,
            calculated_at
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_logistics_dashboard`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'logistics' AND status = 'PUBLISHED'
        )
        ORDER BY order_cohort_month, source_system
    """, domain_check="logistics")



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
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_predictive_metrics`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'predictive' AND status = 'PUBLISHED'
        )
        ORDER BY metric
    """, domain_check="predictive")


@app.get("/api/predictive/predictions")
def predictive_predictions():
    return execute_query(f"""
        SELECT
            semana,
            categoria,
            actual,
            prediccion,
            error_absoluto
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_predictive_predictions`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'predictive' AND status = 'PUBLISHED'
        )
        ORDER BY semana, categoria
    """, domain_check="predictive")


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
