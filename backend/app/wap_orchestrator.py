import os
import time
import random
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from google.cloud import bigquery
from google.api_core.exceptions import (
    GoogleAPICallError,
    InternalServerError,
    ServiceUnavailable,
    GatewayTimeout,
    BadRequest,
    Conflict,
    NotFound
)

logger = logging.getLogger("lumina.wap_orchestrator")

class WAPBusinessError(Exception):
    """Excepción para errores de negocio o validación permanente que NO deben reintentarse."""
    pass

class WAPUncertainStateError(Exception):
    """Excepción cuando tras un timeout la base de datos queda en estado ambiguo no comprobable."""
    pass

class WAPLockAcquisitionError(Exception):
    """Excepción cuando no es posible adquirir el lock tras agotar reintentos."""
    pass

class WAPOrchestrator:
    MANDATORY_TESTS = {
        "commercial": ["TEST_COMM_CURRENCY_ISOLATION", "TEST_COMM_PK_MONTHLY_NOT_NULL", "TEST_COMM_MONTHLY_GRAIN_UNIQUENESS", "TEST_COMM_UCI_NO_INVENTED_CATEGORIES", "TEST_COMM_UCI_GRANULARITY_AND_PRESERVATION", "TEST_COMM_INTEGRITY_MONTHLY_VS_PRODUCTS"],
        "logistics": ["TEST_LOG_UCI_EXCLUDED", "TEST_LOG_SOURCES_ALLOWED", "TEST_LOG_PK_NOT_NULL", "TEST_LOG_UNIQUENESS"],
        "inventory": ["TEST_INV_PK_NOT_NULL", "TEST_INV_NO_CYBER_TEST", "TEST_INV_NO_NEGATIVE_STOCK"],
        "predictive": ["TEST_PRED_METRICS_EXIST", "TEST_PRED_NO_NEGATIVE_PREDS", "TEST_PRED_VALID_DATES"]
    }

    MANDATORY_TABLES = {
        "commercial": ["gold_commercial_monthly", "gold_commercial_categories", "gold_commercial_products"],
        "logistics": ["gold_logistics_dashboard"],
        "inventory": ["gold_inventory_current", "gold_inventory_risks"], 
        "predictive": ["gold_predictive_metrics", "gold_predictive_predictions"]
    }

    def __init__(self, project_id: str = "lumina-retail-001", scripts_dir: Optional[str] = None, client: Optional[bigquery.Client] = None):
        self.project_id = project_id
        self.client = client or bigquery.Client(project=project_id)
        if scripts_dir:
            self.scripts_dir = Path(scripts_dir)
        else:
            self.scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "wap"
            
        if not self.scripts_dir.exists():
            raise FileNotFoundError(f"Directorio de scripts WAP no encontrado: {self.scripts_dir}")

    def load_sql(self, script_name: str) -> str:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Script SQL no existe: {script_path}")
        return script_path.read_text(encoding="utf-8")

    def execute_bq_with_retry(
        self, 
        sql: str, 
        params: List[bigquery.ScalarQueryParameter], 
        step_name: str, 
        domain: str, 
        run_id: str, 
        max_retries: int = 5, 
        initial_wait: float = 60.0,
        max_wait: float = 300.0
    ) -> Any:
        attempt = 0
        last_job_id = None
        while attempt < max_retries:
            job_id = f"wap_{domain}_{run_id}_{step_name.lower()}_{attempt}_{uuid.uuid4().hex[:6]}"
            last_job_id = job_id
            job_config = bigquery.QueryJobConfig(
                query_parameters=params,
                use_legacy_sql=False
            )
            try:
                job = self.client.query(sql, job_config=job_config, job_id=job_id, job_retry=None)
                return job.result()
            except Exception as e:
                msg = str(e)
                logger.warning(f"Excepción en {step_name} (intento {attempt+1}/{max_retries}, job_id={job_id}): {msg}")

                # 1. Errores de Negocio o Sintaxis: NO reintentables
                if "ABORT_BUSINESS" in msg or "Assertion" in msg or isinstance(e, BadRequest):
                    logger.error(f"Fallo de regla de negocio o sintaxis en {step_name}: {msg}")
                    raise WAPBusinessError(f"Fallo permanente en {step_name}: {msg}") from e

                # 2. Pérdida de Respuesta / Timeout: Verificar estado persistido
                if isinstance(e, GatewayTimeout) or "ReadTimeout" in msg or "timeout" in msg.lower():
                    logger.warning(f"Timeout o corte TCP en {step_name}. Verificando estado persistido...")
                    is_done, state_res = self._check_persisted_state(domain, run_id, step_name, last_job_id)
                    if is_done:
                        logger.info(f"Recuperación exitosa: la operación {step_name} se completó en BigQuery.")
                        return state_res
                    else:
                        logger.warning(f"Estado incierto en backend tras timeout. Preparando reintento...")

                # 3. Conflictos de concurrencia OCC: Reintentables con backoff y jitter
                is_transient = any(term in msg for term in [
                    "ABORT_OCC", "concurrent update", "Transaction aborted", "rateLimitExceeded", "503"
                ]) or isinstance(e, (ServiceUnavailable, InternalServerError, Conflict))

                if not is_transient and not isinstance(e, GatewayTimeout):
                    logger.error(f"Error no clasificado como transitorio en {step_name}: {msg}")
                    raise e

                attempt += 1
                if attempt >= max_retries:
                    logger.error(f"Se agotaron los reintentos ({max_retries}) para {step_name}.")
                    raise e

                base_wait = min(max_wait, initial_wait * (2 ** (attempt - 1)))
                jitter = random.uniform(0.8, 1.2)
                sleep_time = base_wait * jitter
                logger.warning(f"Reintentando {step_name} en {sleep_time:.1f}s tras conflicto OCC...")
                time.sleep(sleep_time)

    def _check_persisted_state(self, domain: str, run_id: str, step_name: str, job_id: str) -> Tuple[bool, Any]:
        """Comprueba el estado persistido en tablas de control ante fallos de conexión."""
        try:
            if step_name == "PUBLISH":
                q = """
                SELECT current_run_id, status 
                FROM `lumina-retail-001.lumina_sandbox.gold_release_control` 
                WHERE domain = @domain
                """
                cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("domain", "STRING", domain)])
                rows = list(self.client.query(q, job_config=cfg).result())
                if rows and rows[0]["current_run_id"] == run_id and rows[0]["status"] == "PUBLISHED":
                    return True, rows
            elif step_name == "ACQUIRE":
                q = """
                SELECT status, locked_by_run_id, fencing_token 
                FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock` 
                WHERE domain = @domain
                """
                cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("domain", "STRING", domain)])
                rows = list(self.client.query(q, job_config=cfg).result())
                if rows and rows[0]["status"] == "LOCKED" and rows[0]["locked_by_run_id"] == run_id:
                    return True, rows
            elif step_name == "WRITE":
                q = """
                SELECT COUNT(DISTINCT JSON_VALUE(details, "$.table_name")) as cnt
                FROM `lumina-retail-001.lumina_sandbox.gold_execution_history`
                WHERE run_id = @run_id AND domain = @domain AND operation_type = "WRITE_TABLE" AND event_type = "SUCCESS"
                """
                cfg = bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("domain", "STRING", domain),
                    bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
                ])
                rows = list(self.client.query(q, job_config=cfg).result())
                expected_cnt = len(self.MANDATORY_TABLES.get(domain, []))
                if rows and rows[0]["cnt"] == expected_cnt:
                    return True, rows
        except Exception as e:
            logger.error(f"Error consultando estado de persistencia para {step_name}: {e}")
        return False, None

    def acquire(self, domain: str, run_id: str, max_retries: int = 5) -> int:
        """Adquiere el lock y retorna el fencing_token asignado."""
        if domain not in self.MANDATORY_TABLES:
            raise WAPBusinessError(f"Dominio no soportado: {domain}")
            
        sql = self.load_sql("02_wap_acquire.sql")
        params = [
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
        ]
        
        self.execute_bq_with_retry(sql, params, "ACQUIRE", domain, run_id, max_retries=max_retries, initial_wait=60.0)
        
        # Recuperar y verificar token
        token_sql = """
        SELECT fencing_token 
        FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
        WHERE domain = @domain AND status = "LOCKED" AND locked_by_run_id = @run_id
        """
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(self.client.query(token_sql, job_config=job_config).result())
        if not rows:
            raise WAPLockAcquisitionError(f"No se pudo confirmar la posesión del lock para {domain} y {run_id}")
            
        fencing_token = rows[0]["fencing_token"]
        logger.info(f"Lock adquirido para dominio {domain}, run_id {run_id}, fencing_token={fencing_token}")
        return fencing_token

    def renew_lease(self, domain: str, run_id: str, fencing_token: int) -> bool:
        """Renueva el lease de un lock en posesión activa."""
        sql = """
        UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
        SET leased_until = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
        WHERE domain = @domain 
          AND status = "LOCKED" 
          AND locked_by_run_id = @run_id 
          AND fencing_token = @fencing_token
          AND leased_until >= CURRENT_TIMESTAMP();
        """
        params = [
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("fencing_token", "INT64", fencing_token)
        ]
        cfg = bigquery.QueryJobConfig(query_parameters=params)
        job = self.client.query(sql, job_config=cfg)
        job.result()
        return job.num_dml_affected_rows == 1

    def _write_inventory(self, run_id: str, publish_date: datetime, operator: str, fingerprint: str) -> None:
        """Escribe las tablas Gold de inventory salvando la frontera regional (us-east1 -> US)."""
        q_stock = "SELECT * FROM `lumina-retail-001.lumina_streaming.stock_actual_vw` WHERE (region IS NULL OR region != 'CYBER_TEST')"
        rows_stock = [dict(r) for r in self.client.query(q_stock, location="us-east1").result()]
        
        q_risk = "SELECT * FROM `lumina-retail-001.lumina_streaming.stock_risk_by_product_region` WHERE (region IS NULL OR region != 'CYBER_TEST')"
        rows_risk = [dict(r) for r in self.client.query(q_risk, location="us-east1").result()]

        values_stock = []
        for r in rows_stock:
            pid = repr(str(r["product_id"]))
            reg = repr(str(r["region"]))
            stk = int(r["stock_registrado"])
            fev = f"TIMESTAMP '{r['fecha_ultimo_evento'].isoformat()}'" if r["fecha_ultimo_evento"] else "NULL"
            fpr = f"TIMESTAMP '{r['fecha_procesamiento'].isoformat()}'" if r["fecha_procesamiento"] else "NULL"
            mde = int(r["minutos_desde_evento"]) if r["minutos_desde_evento"] is not None else "NULL"
            efr = repr(str(r["estado_frescura"]))
            est = "'CRITICO'" if stk < 10 else "'BAJO'" if stk <= 20 else "'NORMAL'"
            values_stock.append(f"(@run_id, @publish_date, {pid}, {reg}, {stk}, {fev}, {fpr}, {mde}, {efr}, {est})")

        values_risk = []
        for r in rows_risk:
            pid = repr(str(r["product_id"]))
            reg = repr(str(r["region"]))
            tot = int(r["total_eventos"])
            prm = float(r["stock_promedio"]) if r["stock_promedio"] is not None else "NULL"
            mns = int(r["stock_minimo"]) if r["stock_minimo"] is not None else "NULL"
            mxs = int(r["stock_maximo"]) if r["stock_maximo"] is not None else "NULL"
            alc = int(r["alertas_criticas"]) if r["alertas_criticas"] is not None else "NULL"
            esb = int(r["eventos_stock_bajo"]) if r["eventos_stock_bajo"] is not None else "NULL"
            pal = float(r["porcentaje_alertas"]) if r["porcentaje_alertas"] is not None else "NULL"
            values_risk.append(f"(@run_id, @publish_date, {pid}, {reg}, {tot}, {prm}, {mns}, {mxs}, {alc}, {esb}, {pal})")

        stock_insert_sql = ",\n".join(values_stock)
        risk_insert_sql = ",\n".join(values_risk)

        sql = f"""
        BEGIN
          BEGIN TRANSACTION;
            DELETE FROM `lumina-retail-001.lumina_sandbox.gold_inventory_current` WHERE run_id = @run_id;
            DELETE FROM `lumina-retail-001.lumina_sandbox.gold_inventory_risks` WHERE run_id = @run_id;
            DELETE FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` WHERE run_id = @run_id AND domain = 'inventory' AND operation_type = 'WRITE_TABLE';

            INSERT INTO `lumina-retail-001.lumina_sandbox.gold_inventory_current`
            (run_id, publish_date, product_id, region, stock_registrado, fecha_ultimo_evento, fecha_procesamiento, minutos_desde_evento, estado_frescura, estado_stock)
            VALUES
            {stock_insert_sql};

            INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
            VALUES (GENERATE_UUID(), @run_id, 1, 'WRITE_TABLE', 'inventory', 'SUCCESS', CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT('table_name', 'gold_inventory_current'));

            INSERT INTO `lumina-retail-001.lumina_sandbox.gold_inventory_risks`
            (run_id, publish_date, product_id, region, total_eventos, stock_promedio, stock_minimo, stock_maximo, alertas_criticas, eventos_stock_bajo, porcentaje_alertas)
            VALUES
            {risk_insert_sql};

            INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
            VALUES (GENERATE_UUID(), @run_id, 2, 'WRITE_TABLE', 'inventory', 'SUCCESS', CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT('table_name', 'gold_inventory_risks'));
          COMMIT TRANSACTION;
        EXCEPTION WHEN ERROR THEN
          ROLLBACK TRANSACTION;
          RAISE USING MESSAGE = @@error.message;
        END;
        """
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("publish_date", "TIMESTAMP", publish_date),
            bigquery.ScalarQueryParameter("operator", "STRING", operator),
            bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint)
        ]
        self.execute_bq_with_retry(sql, params, "WRITE", "inventory", run_id)
        logger.info(f"Fase WRITE completada exitosamente para dominio inventory y run_id {run_id}")

    def write(self, domain: str, run_id: str, publish_date: datetime, operator: str = "orchestrator", fingerprint: str = "N/A") -> None:
        """Materializa las tablas Gold correspondientes al dominio dentro de una transacción."""
        if domain == "inventory":
            return self._write_inventory(run_id, publish_date, operator, fingerprint)

        script_map = {
            "commercial": "03a_wap_write_commercial.sql",
            "logistics": "03b_wap_write_logistics.sql",
            "predictive": "03d_wap_write_predictive.sql"
        }
        script_name = script_map[domain]
        sql = self.load_sql(script_name)
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("publish_date", "TIMESTAMP", publish_date),
            bigquery.ScalarQueryParameter("operator", "STRING", operator),
            bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint)
        ]
        self.execute_bq_with_retry(sql, params, "WRITE", domain, run_id)
        logger.info(f"Fase WRITE completada exitosamente para dominio {domain} y run_id {run_id}")

    def audit(self, domain: str, run_id: str, audit_timestamp: datetime, catalog_version: str = "1.0.0") -> None:
        """Ejecuta el catálogo de auditorías para el run_id y dominio."""
        script_map = {"commercial": "04a_wap_audit_commercial.sql", "logistics": "04b_wap_audit_logistics.sql", "inventory": "04c_wap_audit_inventory.sql", "predictive": "04d_wap_audit_predictive.sql"}; script_name = script_map[domain]
        sql = self.load_sql(script_name)
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("audit_timestamp", "TIMESTAMP", audit_timestamp),
            bigquery.ScalarQueryParameter("catalog_version", "STRING", catalog_version)
        ]
        self.execute_bq_with_retry(sql, params, "AUDIT", domain, run_id)
        logger.info(f"Fase AUDIT completada exitosamente para dominio {domain} y run_id {run_id}")

    def publish(
        self, 
        domain: str, 
        run_id: str, 
        fencing_token: int, 
        expected_previous_run_id: Optional[str] = None, 
        catalog_version: str = "1.0.0"
    ) -> None:
        """Ejecuta la transacción atómica de publicación en BigQuery."""
        sql = self.load_sql("05_wap_publish.sql")
        params = [
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("mem_fencing_token", "INT64", fencing_token),
            bigquery.ScalarQueryParameter("expected_previous_run_id", "STRING", expected_previous_run_id),
            bigquery.ScalarQueryParameter("catalog_version", "STRING", catalog_version),
            bigquery.ArrayQueryParameter("mandatory_tests", "STRING", self.MANDATORY_TESTS[domain]),
            bigquery.ArrayQueryParameter("mandatory_tables", "STRING", self.MANDATORY_TABLES[domain]),
            bigquery.ScalarQueryParameter("seq_publish", "INT64", 99)
        ]
        self.execute_bq_with_retry(sql, params, "PUBLISH", domain, run_id)
        logger.info(f"Fase PUBLISH completada exitosamente. Versión {run_id} publicada en {domain}")

    def rollback(self, domain: str, rollback_run_id: str, bad_run_id: str, target_run_id: str) -> None:
        """Ejecuta el procedimiento atómico de rollback hacia target_run_id."""
        sql = self.load_sql("06_wap_rollback.sql")
        params = [
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("rollback_run_id", "STRING", rollback_run_id),
            bigquery.ScalarQueryParameter("bad_run_id", "STRING", bad_run_id),
            bigquery.ScalarQueryParameter("target_run_id", "STRING", target_run_id),
            bigquery.ArrayQueryParameter("mandatory_tests", "STRING", self.MANDATORY_TESTS[domain]),
            bigquery.ArrayQueryParameter("mandatory_tables", "STRING", self.MANDATORY_TABLES[domain])
        ]
        self.execute_bq_with_retry(sql, params, "ROLLBACK", domain, rollback_run_id)
        logger.info(f"Rollback exitoso en dominio {domain}: revertido {bad_run_id} -> restaurado {target_run_id}")

    def _safe_release_lock(self, domain: str, run_id: str, fencing_token: int) -> None:
        """Libera el lock de forma segura y condicional solo si la posesión es legítima."""
        try:
            sql = """
            UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
            SET status = "FREE", locked_by_run_id = NULL, last_published_at = CURRENT_TIMESTAMP()
            WHERE domain = @domain 
              AND status = "LOCKED" 
              AND locked_by_run_id = @run_id 
              AND fencing_token = @fencing_token;
            """
            cfg = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("domain", "STRING", domain),
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("fencing_token", "INT64", fencing_token)
            ])
            self.client.query(sql, job_config=cfg).result()
            logger.info(f"Lock liberado de forma segura tras interrupción/fallo en {domain}")
        except Exception as e:
            logger.error(f"Error liberando lock de forma segura: {e}")

    def get_current_release(self, domain: str) -> Optional[str]:
        """Obtiene la versión actualmente publicada de un dominio."""
        sql = """
        SELECT current_run_id 
        FROM `lumina-retail-001.lumina_sandbox.gold_release_control` 
        WHERE domain = @domain AND status = "PUBLISHED"
        """
        cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("domain", "STRING", domain)])
        rows = list(self.client.query(sql, job_config=cfg).result())
        return rows[0]["current_run_id"] if rows else None

    def run_pipeline(self, domain: str, operator: str = "orchestrator", catalog_version: str = "1.0.0") -> str:
        """Ejecuta el ciclo de vida completo WAP: ACQUIRE -> WRITE -> AUDIT -> PUBLISH."""
        run_id = f"run_{domain}_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)
        fencing_token = None
        
        expected_prev_run = self.get_current_release(domain)
        logger.info(f"Iniciando WAP pipeline: domain={domain}, run_id={run_id}, expected_prev={expected_prev_run}")

        try:
            # 1. ACQUIRE
            fencing_token = self.acquire(domain, run_id)
            
            # 2. WRITE
            self.write(domain, run_id, publish_date=now, operator=operator, fingerprint="FINGERPRINT_VERIFIED")
            
            # Renovación preventiva del lease tras escritura pesada
            self.renew_lease(domain, run_id, fencing_token)
            
            # 3. AUDIT
            self.audit(domain, run_id, audit_timestamp=now, catalog_version=catalog_version)
            
            # Renovación preventiva del lease tras auditoría
            self.renew_lease(domain, run_id, fencing_token)
            
            # 4. PUBLISH
            self.publish(domain, run_id, fencing_token, expected_previous_run_id=expected_prev_run, catalog_version=catalog_version)
            logger.info(f"Pipeline WAP completado exitosamente para {domain}: {run_id}")
            return run_id
            
        except Exception as e:
            logger.error(f"Fallo en ejecución del pipeline WAP para {domain} ({run_id}): {e}")
            if fencing_token:
                self._safe_release_lock(domain, run_id, fencing_token)
            raise e
