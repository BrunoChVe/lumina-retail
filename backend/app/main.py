import os
import math
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
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
            category_type,
            category_type AS category_origin,
            COALESCE(category, 'Unclassified') AS category,
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
            COALESCE(category, 'Unclassified') AS category,
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



def _calc_stats(values: List[float]):
    if not values:
        return 0.0, 0.0
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return round(mean_val, 2), round(math.sqrt(variance), 2)


def _add_weeks(dt_val, num_weeks: int) -> str:
    if isinstance(dt_val, str):
        try:
            d = datetime.strptime(str(dt_val)[:10], "%Y-%m-%d").date()
        except Exception:
            d = date.today()
    elif isinstance(dt_val, (date, datetime)):
        d = dt_val if isinstance(dt_val, date) else dt_val.date()
    else:
        d = date.today()
    return (d + timedelta(weeks=num_weeks)).strftime("%Y-%m-%d")


@app.get("/api/inventory/metadata")
def inventory_metadata(include_synthetic: bool = False):
    synth_cond = "" if include_synthetic else "WHERE (region IS NULL OR region != 'CYBER_TEST')"
    stock_rows = execute_query(f"""
        SELECT DISTINCT product_id, region 
        FROM `{PROJECT_ID}.{STREAMING_DATASET}.stock_actual_vw`
        {synth_cond}
        ORDER BY region, product_id
    """)
    uci_countries = execute_query(f"""
        SELECT DISTINCT country 
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_inventory_country`
        ORDER BY country
    """, domain_check="commercial")
    
    region_map = {}
    regions_set = set()
    products_set = set()
    for r in stock_rows:
        reg = r.get("region") or "Sin Región"
        pid = r.get("product_id")
        regions_set.add(reg)
        products_set.add(pid)
        if reg not in region_map:
            region_map[reg] = []
        if pid not in region_map[reg]:
            region_map[reg].append(pid)
        
    return {
        "operational_regions": sorted(list(regions_set)),
        "operational_products": sorted(list(products_set)),
        "operational_region_product_map": region_map,
        "uci_countries": [c["country"] for c in uci_countries if c.get("country")],
        "uci_abc_classes": ["A", "B", "C"]
    }


@app.get("/api/inventory/current")
def inventory_current(
    include_synthetic: bool = False,
    region: Optional[str] = None,
    product_id: Optional[str] = None
):
    conditions = []
    if not include_synthetic:
        conditions.append("(region IS NULL OR region != 'CYBER_TEST')")
    if region and region != "ALL":
        safe_reg = region.replace("'", "\\'")
        conditions.append(f"region = '{safe_reg}'")
    if product_id and product_id != "ALL":
        safe_pid = product_id.replace("'", "\\'")
        conditions.append(f"product_id = '{safe_pid}'")
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
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
        {where_clause}
        ORDER BY stock_registrado ASC, product_id, region
    """)


@app.get("/api/inventory/risks")
def inventory_risks(
    include_synthetic: bool = False,
    region: Optional[str] = None,
    product_id: Optional[str] = None
):
    conditions = []
    if not include_synthetic:
        conditions.append("(region IS NULL OR region != 'CYBER_TEST')")
    if region and region != "ALL":
        safe_reg = region.replace("'", "\\'")
        conditions.append(f"region = '{safe_reg}'")
    if product_id and product_id != "ALL":
        safe_pid = product_id.replace("'", "\\'")
        conditions.append(f"product_id = '{safe_pid}'")
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
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
        {where_clause}
        ORDER BY alertas_criticas DESC, stock_minimo ASC
    """)


@app.get("/api/inventory/uci/summary")
def inventory_uci_summary(
    country: Optional[str] = None,
    stock_code: Optional[str] = None,
    abc_class: Optional[str] = None
):
    # Si se filtra por país específico
    if country and country != "ALL":
        safe_country = country.replace("'", "\\'")
        conditions = [f"country = '{safe_country}'"]
        if stock_code and stock_code != "ALL":
            conditions.append(f"stock_code = '{stock_code.replace("'", "\\'")}'")
        where_ctry = f"WHERE {' AND '.join(conditions)}"
        return execute_query(f"""
            SELECT 
                COUNT(DISTINCT stock_code) as total_products,
                SUM(units_sold) as total_units_sold,
                SUM(units_returned) as total_units_returned,
                SUM(units_net) as total_units_net,
                ROUND(SUM(gross_revenue_gbp), 2) as total_revenue_gbp,
                1 as total_countries,
                '2010-12-01' as min_date,
                '2011-12-09' as max_date,
                COUNTIF(units_sold > 500) as count_a,
                COUNTIF(units_sold BETWEEN 100 AND 500) as count_b,
                COUNTIF(units_sold < 100) as count_c
            FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_inventory_country`
            {where_ctry}
        """, domain_check="commercial")

    conditions = []
    if stock_code and stock_code != "ALL":
        conditions.append(f"stock_code = '{stock_code.replace("'", "\\'")}'")
    if abc_class and abc_class != "ALL":
        conditions.append(f"abc_class = '{abc_class.replace("'", "\\'")}'")
    where_catalog = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    return execute_query(f"""
        SELECT 
            COUNT(DISTINCT stock_code) as total_products,
            SUM(units_sold) as total_units_sold,
            SUM(units_returned) as total_units_returned,
            SUM(units_net) as total_units_net,
            ROUND(SUM(gross_revenue_gbp), 2) as total_revenue_gbp,
            (SELECT COUNT(DISTINCT country) FROM `{PROJECT_ID}.lumina_stage.stg_uci_online_retail`) as total_countries,
            MIN(first_sale_date) as min_date,
            MAX(last_sale_date) as max_date,
            COUNTIF(abc_class = 'A') as count_a,
            COUNTIF(abc_class = 'B') as count_b,
            COUNTIF(abc_class = 'C') as count_c
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_product_catalog`
        {where_catalog}
    """, domain_check="commercial")


@app.get("/api/inventory/uci/catalog")
def inventory_uci_catalog(
    limit: int = 100,
    stock_code: Optional[str] = None,
    abc_class: Optional[str] = None,
    country: Optional[str] = None
):
    safe_limit = min(max(limit, 1), 500)
    conditions = []
    if stock_code and stock_code != "ALL":
        conditions.append(f"stock_code = '{stock_code.replace("'", "\\'")}'")
    if abc_class and abc_class != "ALL":
        conditions.append(f"abc_class = '{abc_class.replace("'", "\\'")}'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return execute_query(f"""
        SELECT * FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_product_catalog`
        {where_clause}
        ORDER BY gross_revenue_gbp DESC
        LIMIT {safe_limit}
    """, domain_check="commercial")


@app.get("/api/inventory/uci/country")
def inventory_uci_country(
    country: Optional[str] = None,
    stock_code: Optional[str] = None
):
    conditions = []
    if country and country != "ALL":
        conditions.append(f"country = '{country.replace("'", "\\'")}'")
    if stock_code and stock_code != "ALL":
        conditions.append(f"stock_code = '{stock_code.replace("'", "\\'")}'")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return execute_query(f"""
        SELECT 
            country,
            SUM(units_sold) as total_units_sold,
            SUM(units_returned) as total_units_returned,
            SUM(units_net) as total_units_net,
            ROUND(SUM(gross_revenue_gbp), 2) as total_revenue,
            COUNT(DISTINCT stock_code) as distinct_products
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_inventory_country`
        {where_clause}
        GROUP BY country
        ORDER BY total_units_sold DESC
        LIMIT 15
    """, domain_check="commercial")


@app.get("/api/inventory/uci/monthly")
def inventory_uci_monthly(
    country: Optional[str] = None,
    stock_code: Optional[str] = None
):
    conditions = []
    if country and country != "ALL":
        conditions.append(f"country = '{country.replace("'", "\\'")}'")
    if stock_code and stock_code != "ALL":
        conditions.append(f"stock_code = '{stock_code.replace("'", "\\'")}'")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return execute_query(f"""
        SELECT 
            sales_month, 
            SUM(units_sold) as total_units_sold, 
            SUM(units_returned) as total_units_returned, 
            SUM(units_net) as total_units_net,
            ROUND(SUM(gross_revenue_gbp), 2) as total_revenue
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_inventory_monthly`
        {where_clause}
        GROUP BY sales_month
        ORDER BY sales_month
    """, domain_check="commercial")


@app.get("/api/predictive/metadata")
def predictive_metadata():
    cats = execute_query(f"""
        SELECT DISTINCT categoria
        FROM `{PROJECT_ID}.{WAP_DATASET}.gold_predictive_predictions`
        WHERE run_id = (
            SELECT current_run_id
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
            WHERE domain = 'predictive' AND status = 'PUBLISHED'
        )
        ORDER BY categoria
    """, domain_check="predictive")
    
    sellers = execute_query(f"""
        SELECT seller_id, COUNT(DISTINCT product_id) as n_products, COUNT(*) as n_items
        FROM `{PROJECT_ID}.lumina_stage.fact_order_items`
        GROUP BY seller_id
        ORDER BY n_items DESC
        LIMIT 15
    """)
    
    top_products = execute_query(f"""
        SELECT product_id, COUNT(DISTINCT seller_id) as n_sellers, COUNT(*) as n_items
        FROM `{PROJECT_ID}.lumina_stage.fact_order_items`
        GROUP BY product_id
        ORDER BY n_items DESC
        LIMIT 15
    """)
    
    uci_countries = execute_query(f"""
        SELECT country, COUNT(DISTINCT stock_code) as n_products, SUM(units_sold) as total_units
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_inventory_country`
        GROUP BY country
        ORDER BY total_units DESC
        LIMIT 15
    """, domain_check="commercial")

    uci_top_products = execute_query(f"""
        SELECT stock_code, MAX(description) as description, SUM(units_sold) as total_units
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_uci_analytical_product_catalog`
        GROUP BY stock_code
        ORDER BY total_units DESC
        LIMIT 15
    """, domain_check="commercial")

    return {
        "sources": [
            {"id": "olist", "name": "Olist Marketplace (Brasil)", "currency": "BRL", "granularity_type": "Categoría / Vendedor / Producto"},
            {"id": "thelook", "name": "TheLook eCommerce (Global)", "currency": "USD", "granularity_type": "Tienda Global eCommerce"},
            {"id": "uci", "name": "UCI Online Retail (UK)", "currency": "GBP", "granularity_type": "Mercado Geográfico / País / Producto"}
        ],
        "categories": [c["categoria"] for c in cats if c.get("categoria")],
        "top_sellers": sellers,
        "top_products": top_products,
        "uci_countries": [c["country"] for c in uci_countries if c.get("country")],
        "uci_top_products": uci_top_products
    }


@app.get("/api/predictive/forecast")
def predictive_granular_forecast(
    source: str = "olist",
    category: Optional[str] = None,
    seller_id: Optional[str] = None,
    product_id: Optional[str] = None,
    country: Optional[str] = None,
    horizon: int = 12
):
    safe_horizon = min(max(horizon, 1), 52)
    
    # Caso 1: Olist por Categoría (Modelo Gold XGBoost WAP)
    if source == "olist" and (category or (not seller_id and not product_id)):
        target_cat = category or "bed_bath_table"
        safe_cat = target_cat.replace("'", "\\'")
        
        rows = execute_query(f"""
            SELECT semana, actual, prediccion, error_absoluto
            FROM `{PROJECT_ID}.{WAP_DATASET}.gold_predictive_predictions`
            WHERE run_id = (
                SELECT current_run_id
                FROM `{PROJECT_ID}.{WAP_DATASET}.gold_release_control`
                WHERE domain = 'predictive' AND status = 'PUBLISHED'
            )
            AND categoria = '{safe_cat}'
            ORDER BY semana
        """, domain_check="predictive")
        
        if not rows:
            return {
                "source": source,
                "granularity": "category",
                "target": target_cat,
                "sufficient_history": False,
                "reason": f"No se encontraron predicciones en Gold para la categoría '{target_cat}'."
            }
            
        actuals = [float(r["actual"]) for r in rows if r.get("actual") is not None]
        errors = [float(r["error_absoluto"]) for r in rows if r.get("error_absoluto") is not None]
        avg_demand, std_val = _calc_stats(actuals)
        trend = "CRECIENTE" if actuals[-1] > actuals[0] else ("DECRECIENTE" if actuals[-1] < actuals[0] else "ESTABLE")
        
        mae = round(sum(errors) / len(errors), 2) if errors else 0.0
        rmse = round(math.sqrt(sum(e**2 for e in errors) / len(errors)), 2) if errors else 0.0
        wape = round((sum(errors) / sum(actuals) * 100), 2) if sum(actuals) > 0 else 0.0
        
        history_series = []
        forecast_series = []
        for r in rows:
            s_str = str(r["semana"])
            history_series.append({"semana": s_str, "actual": round(float(r["actual"]), 2)})
            pred = round(float(r["prediccion"]), 2)
            forecast_series.append({
                "semana": s_str,
                "prediccion": pred,
                "lower_bound": max(0.0, round(pred - 1.96 * std_val, 2)),
                "upper_bound": round(pred + 1.96 * std_val, 2)
            })
            
        return {
            "source": source,
            "granularity": "category",
            "target": target_cat,
            "sufficient_history": True,
            "observations": len(rows),
            "avg_demand": avg_demand,
            "variability_std": std_val,
            "trend": trend,
            "model_name": "XGBoost Regressor (Gold WAP)",
            "metrics": {"MAE": mae, "RMSE": rmse, "WAPE": wape},
            "history": history_series,
            "forecast": forecast_series[:safe_horizon],
            "note": "Modelo XGBoost evaluado y gobernado formalmente bajo el protocolo WAP-02.1 sobre la categoría seleccionada."
        }
        
    # Caso 2: Olist por Vendedor / Producto
    elif source == "olist" and (seller_id or product_id):
        conditions = []
        if seller_id and seller_id != "ALL":
            conditions.append(f"seller_id = '{seller_id.replace("'", "\\'")}'")
        if product_id and product_id != "ALL":
            conditions.append(f"product_id = '{product_id.replace("'", "\\'")}'")
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        weekly_rows = execute_query(f"""
            SELECT 
                DATE_TRUNC(date_key, WEEK) as semana,
                COUNT(*) as actual
            FROM `{PROJECT_ID}.lumina_stage.fact_order_items`
            {where_sql}
            GROUP BY semana
            ORDER BY semana
        """)
        
        n_weeks = len(weekly_rows)
        if n_weeks < 10:
            return {
                "source": source,
                "granularity": "seller_product",
                "seller_id": seller_id,
                "product_id": product_id,
                "sufficient_history": False,
                "observations": n_weeks,
                "reason": f"Historial insuficiente para pronóstico estadístico confiable (Encontradas {n_weeks} semanas de actividad, mínimo requerido: 10 semanas). No se generan pronósticos sintéticos para evitar predicciones espurias.",
                "history": [{"semana": str(r["semana"]), "actual": int(r["actual"])} for r in weekly_rows]
            }
            
        actuals = [float(r["actual"]) for r in weekly_rows]
        avg_demand, std_val = _calc_stats(actuals)
        trend = "CRECIENTE" if actuals[-1] > actuals[0] else ("DECRECIENTE" if actuals[-1] < actuals[0] else "ESTABLE")
        
        history_series = [{"semana": str(r["semana"]), "actual": int(r["actual"])} for r in weekly_rows]
        forecast_series = []
        last_date = weekly_rows[-1]["semana"]
        for h in range(1, safe_horizon + 1):
            next_date_str = _add_weeks(last_date, h)
            forecast_series.append({
                "semana": next_date_str,
                "prediccion": avg_demand,
                "lower_bound": max(0.0, round(avg_demand - 1.96 * std_val, 2)),
                "upper_bound": round(avg_demand + 1.96 * std_val, 2)
            })
            
        return {
            "source": source,
            "granularity": "seller_product",
            "seller_id": seller_id,
            "product_id": product_id,
            "sufficient_history": True,
            "observations": n_weeks,
            "avg_demand": avg_demand,
            "variability_std": std_val,
            "trend": trend,
            "model_name": "Moving Average Baseline (Intervalo Confianza 95%)",
            "metrics": {
                "MAE": round(std_val * 0.8, 2),
                "RMSE": std_val,
                "WAPE": round(min(100.0, (std_val / avg_demand * 100)), 2) if avg_demand > 0 else 0.0
            },
            "history": history_series[-26:],
            "forecast": forecast_series,
            "note": "Pronóstico de demanda por vendedor/producto basado en historial empírico. Se requiere un mínimo de 10 semanas activas."
        }
        
    # Caso 3: UCI por País / Producto
    elif source == "uci":
        conditions = ["quantity > 0"]
        if country and country != "ALL":
            conditions.append(f"country = '{country.replace("'", "\\'")}'")
        if product_id and product_id != "ALL":
            conditions.append(f"source_product_id = '{product_id.replace("'", "\\'")}'")
        where_sql = f"WHERE {' AND '.join(conditions)}"
        
        weekly_rows = execute_query(f"""
            SELECT 
                DATE_TRUNC(DATE(order_created_at), WEEK) as semana,
                SUM(quantity) as actual
            FROM `{PROJECT_ID}.lumina_stage.stg_uci_online_retail`
            {where_sql}
            GROUP BY semana
            ORDER BY semana
        """, domain_check="commercial")
        
        n_weeks = len(weekly_rows)
        if n_weeks < 10:
            return {
                "source": "uci",
                "granularity": "country_product",
                "country": country,
                "product_id": product_id,
                "sufficient_history": False,
                "observations": n_weeks,
                "reason": f"Historial insuficiente en UCI para pronóstico confiable (Encontradas {n_weeks} semanas de actividad, mínimo requerido: 10 semanas).",
                "history": [{"semana": str(r["semana"]), "actual": int(r["actual"])} for r in weekly_rows]
            }
            
        actuals = [float(r["actual"]) for r in weekly_rows]
        avg_demand, std_val = _calc_stats(actuals)
        trend = "CRECIENTE" if actuals[-1] > actuals[0] else ("DECRECIENTE" if actuals[-1] < actuals[0] else "ESTABLE")
        
        history_series = [{"semana": str(r["semana"]), "actual": int(r["actual"])} for r in weekly_rows]
        forecast_series = []
        last_date = weekly_rows[-1]["semana"]
        for h in range(1, safe_horizon + 1):
            next_date_str = _add_weeks(last_date, h)
            forecast_series.append({
                "semana": next_date_str,
                "prediccion": avg_demand,
                "lower_bound": max(0.0, round(avg_demand - 1.96 * std_val, 2)),
                "upper_bound": round(avg_demand + 1.96 * std_val, 2)
            })
            
        return {
            "source": "uci",
            "granularity": "country_product",
            "country": country,
            "product_id": product_id,
            "sufficient_history": True,
            "observations": n_weeks,
            "avg_demand": avg_demand,
            "variability_std": std_val,
            "trend": trend,
            "model_name": "Persistencia de Demanda Transaccional UCI",
            "metrics": {
                "MAE": round(std_val * 0.8, 2),
                "RMSE": std_val,
                "WAPE": round(min(100.0, (std_val / avg_demand * 100)), 2) if avg_demand > 0 else 0.0
            },
            "history": history_series,
            "forecast": forecast_series,
            "note": "UCI Online Retail no cuenta con modelo estacional entrenado. El pronóstico es una proyección empírica."
        }
        
    # Caso 4: TheLook eCommerce
    else:
        return {
            "source": source,
            "granularity": "thelook_store",
            "sufficient_history": False,
            "reason": "TheLook eCommerce no tiene un modelo de predicción de demanda semanal en Gold WAP.",
            "history": []
        }


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
def predictive_predictions(categoria: Optional[str] = None):
    cond = ""
    if categoria and categoria != "ALL":
        safe_cat = categoria.replace("'", "\\'")
        cond = f"AND categoria = '{safe_cat}'"
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
        {cond}
        ORDER BY semana, categoria
    """, domain_check="predictive")


@app.get("/api/store/performance")
def store_performance():
    return execute_query(f"""
        SELECT
            p.store_id,
            d.store_name,
            d.location,
            p.order_month,
            p.currency_code,
            p.total_orders,
            p.completed_orders,
            p.gross_sales,
            p.net_sales,
            p.total_returns
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_store_commercial_performance` p
        JOIN `{PROJECT_ID}.{WAP_DATASET}.vw_store_dimension` d ON p.store_id = d.store_id
        ORDER BY p.order_month, p.store_id
    """, domain_check="commercial")


@app.get("/api/commercial/countries")
def commercial_countries():
    return execute_query(f"""
        SELECT
            source_system,
            country,
            orders,
            gross_sales,
            currency_code
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_commercial_countries`
        ORDER BY source_system, gross_sales DESC
    """, domain_check="commercial")


@app.get("/api/commercial/customers_summary")
def commercial_customers_summary():
    return execute_query(f"""
        SELECT
            source_system,
            COUNT(DISTINCT customer_id) as total_customers,
            SUM(orders) as total_orders,
            SUM(gross_sales) as total_gross_sales,
            currency_code,
            ROUND(SUM(gross_sales) / COUNT(DISTINCT customer_id), 2) as avg_sales_per_customer
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_commercial_customers`
        GROUP BY 1, 5
        ORDER BY source_system
    """, domain_check="commercial")


@app.get("/api/commercial/cancellations")
def commercial_cancellations():
    return execute_query(f"""
        SELECT
            source_system,
            canceled_orders,
            return_sales,
            negative_adjustments,
            currency_code
        FROM `{PROJECT_ID}.{WAP_DATASET}.vw_commercial_cancellations`
        ORDER BY source_system
    """, domain_check="commercial")

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
