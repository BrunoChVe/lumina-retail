import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone
import uuid

from google.api_core.exceptions import BadRequest, GatewayTimeout, Conflict, ServiceUnavailable
from backend.app.wap_orchestrator import (
    WAPOrchestrator,
    WAPBusinessError,
    WAPLockAcquisitionError
)

class TestWAPAcceptance(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        # Inicializar orquestador con mock
        self.orchestrator = WAPOrchestrator(
            project_id="lumina-retail-001",
            scripts_dir=None,
            client=self.mock_client
        )

    def test_cp01_successful_publish(self):
        """CP-01: Publicación exitosa completa de pipeline commercial."""
        # Mock get_current_release
        self.orchestrator.get_current_release = MagicMock(return_value="prev_run_123")
        
        # Mock acquire query result (token=42)
        mock_acquire_job = MagicMock()
        mock_token_job = MagicMock()
        mock_token_job.result.return_value = [{"fencing_token": 42}]
        
        # Mock write, renew, audit, publish jobs
        mock_dml_job = MagicMock()
        mock_dml_job.result.return_value = []
        mock_dml_job.num_dml_affected_rows = 1

        self.mock_client.query.side_effect = [
            mock_acquire_job,   # SCRIPT 02 UPDATE
            mock_token_job,     # SELECT fencing_token
            mock_dml_job,       # SCRIPT 03a WRITE
            mock_dml_job,       # renew_lease post-write
            mock_dml_job,       # SCRIPT 04a AUDIT
            mock_dml_job,       # renew_lease post-audit
            mock_dml_job        # SCRIPT 05 PUBLISH
        ]

        run_id = self.orchestrator.run_pipeline("commercial", operator="sre_test")
        self.assertTrue(run_id.startswith("run_commercial_"))
        self.assertEqual(self.mock_client.query.call_count, 7)

    def test_cp02_two_concurrent_acquires(self):
        """CP-02: Dos orquestadores concurrentes; el segundo sufre conflicto OCC y reintenta."""
        # Simular primer intento con fallo OCC de BigQuery y segundo intento exitoso
        mock_fail = Conflict("400 Transaction aborted due to concurrent update")
        mock_success_job = MagicMock()
        mock_token_job = MagicMock()
        mock_token_job.result.return_value = [{"fencing_token": 15}]

        self.mock_client.query.side_effect = [mock_fail, mock_success_job, mock_token_job]

        with patch("time.sleep", return_value=None): # Evitar delay real de 60s
            token = self.orchestrator.acquire("commercial", "run_test_occ", max_retries=2)
            self.assertEqual(token, 15)
            self.assertEqual(self.mock_client.query.call_count, 3)

    def test_cp03_lock_occupied(self):
        """CP-03: Lock ocupado por otro proceso; se agotan reintentos y lanza WAPLockAcquisitionError."""
        # El DML UPDATE arroja ABORT_OCC: LOCK_NOT_ACQUIRED
        mock_busy = BadRequest("ABORT_OCC: LOCK_NOT_ACQUIRED")
        self.mock_client.query.side_effect = mock_busy

        with patch("time.sleep", return_value=None):
            with self.assertRaises(Exception) as ctx:
                self.orchestrator.acquire("commercial", "run_test_busy", max_retries=2)
            self.assertTrue("ABORT_OCC" in str(ctx.exception) or "agotados" in str(ctx.exception))

    def test_cp04_expired_lease(self):
        """CP-04: Lock con lease vencido; la consulta UPDATE condicional lo roba e incrementa token."""
        mock_acquire_job = MagicMock()
        mock_token_job = MagicMock()
        mock_token_job.result.return_value = [{"fencing_token": 8}] # Token incrementado

        self.mock_client.query.side_effect = [mock_acquire_job, mock_token_job]

        token = self.orchestrator.acquire("logistics", "run_stolen_lease")
        self.assertEqual(token, 8)

    def test_cp05_invalid_fencing_token(self):
        """CP-05: Fencing token inválido en PUBLISH; BigQuery aborta la transacción."""
        mock_fail = BadRequest("ABORT_OCC: Fallo en renovación de lease. Lock robado, expirado o ABA obsoleto.")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError) as ctx:
            self.orchestrator.publish("commercial", "run_candidate_1", fencing_token=10)
        self.assertIn("ABORT_OCC", str(ctx.exception))

    def test_cp06_error_during_commercial_write(self):
        """CP-06: Error en escritura comercial; el orquestador aborta y libera el lock de forma segura."""
        self.orchestrator.get_current_release = MagicMock(return_value="prev_1")
        self.orchestrator.acquire = MagicMock(return_value=12)
        self.orchestrator._safe_release_lock = MagicMock()

        # Simular error en WRITE
        self.orchestrator.write = MagicMock(side_effect=Exception("BigQuery query error in view"))

        with self.assertRaises(Exception) as ctx:
            self.orchestrator.run_pipeline("commercial")
            
        self.assertIn("BigQuery query error in view", str(ctx.exception))
        self.orchestrator._safe_release_lock.assert_called_once()

    def test_cp07_error_during_logistics_write(self):
        """CP-07: Error durante escritura logística; asegura que no se intenta publicar y se libera lock."""
        self.orchestrator.get_current_release = MagicMock(return_value=None)
        self.orchestrator.acquire = MagicMock(return_value=5)
        self.orchestrator._safe_release_lock = MagicMock()

        self.orchestrator.write = MagicMock(side_effect=WAPBusinessError("Error en logistics write"))

        with self.assertRaises(WAPBusinessError):
            self.orchestrator.run_pipeline("logistics")

        self.orchestrator._safe_release_lock.assert_called_once()

    def test_cp08_audit_failed(self):
        """CP-08: Auditoría fallida; PUBLISH detecta passed=FALSE y aborta la transacción."""
        mock_fail = BadRequest("ABORT_BUSINESS: Catálogo de auditorías incompleto, alterado, con fallos o duplicados.")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError) as ctx:
            self.orchestrator.publish("commercial", "run_bad_audit", fencing_token=1)
        self.assertIn("ABORT_BUSINESS", str(ctx.exception))

    def test_cp09_missing_audit_test(self):
        """CP-09: Falta un test obligatorio en audit_results; el ASSERT de PUBLISH revierte."""
        mock_fail = BadRequest("ABORT_BUSINESS: Catálogo de auditorías incompleto")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError):
            self.orchestrator.publish("logistics", "run_missing_test", fencing_token=1)

    def test_cp10_duplicate_audit_test(self):
        """CP-10: Test duplicado en audit_results; detectado por HAVING COUNT(*) > 1 en PUBLISH."""
        mock_fail = BadRequest("ABORT_BUSINESS: Catálogo de auditorías incompleto, alterado, con fallos o duplicados.")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError):
            self.orchestrator.publish("commercial", "run_dup_test", fencing_token=1)

    def test_cp11_unexpected_manifest_event(self):
        """CP-11: Evento inesperado o tabla faltante en execution_history; PUBLISH aborta."""
        mock_fail = BadRequest("ABORT_BUSINESS: Manifiesto de tablas incompleto, con fallos o duplicados.")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError):
            self.orchestrator.publish("commercial", "run_bad_manifest", fencing_token=1)

    def test_cp12_timeout_during_publish_not_committed(self):
        """CP-12: GatewayTimeout en PUBLISH y DB confirma que NO se publicó; lanza excepción."""
        mock_timeout = GatewayTimeout("504 Gateway Timeout")
        self.mock_client.query.side_effect = mock_timeout

        # Mock de verificación en DB que retorna que sigue en versión antigua
        self.orchestrator._check_persisted_state = MagicMock(return_value=(False, None))

        with patch("time.sleep", return_value=None):
            with self.assertRaises(Exception):
                self.orchestrator.publish("commercial", "run_timeout_uncommitted", fencing_token=1)

    def test_cp13_timeout_during_publish_committed(self):
        """CP-13: GatewayTimeout en PUBLISH pero la DB confirma que SÍ se completó el COMMIT; éxito transparente."""
        mock_timeout = GatewayTimeout("504 Gateway Timeout")
        self.mock_client.query.side_effect = mock_timeout

        # Mock de verificación en DB que confirma que el run_id ya es current_run_id en release_control
        self.orchestrator._check_persisted_state = MagicMock(return_value=(True, [{"current_run_id": "run_timeout_ok"}]))

        # No debe lanzar excepción, se recupera transparentemente
        res = self.orchestrator.publish("commercial", "run_timeout_ok", fencing_token=1)
        self.assertIsNone(res)

    def test_cp14_successful_rollback(self):
        """CP-14: Rollback exitoso hacia un target_run_id previamente publicado."""
        mock_job = MagicMock()
        mock_job.result.return_value = []
        self.mock_client.query.return_value = mock_job

        self.orchestrator.rollback(
            domain="commercial",
            rollback_run_id="run_rollback_01",
            bad_run_id="run_defectuoso",
            target_run_id="run_estable_previo"
        )
        self.mock_client.query.assert_called_once()

    def test_cp15_invalid_rollback_target(self):
        """CP-15: Rollback hacia un target inexistente o nunca publicado; aborta transacción."""
        mock_fail = BadRequest("ABORT_BUSINESS: El target_run_id no es un release válido.")
        self.mock_client.query.side_effect = mock_fail

        with self.assertRaises(WAPBusinessError):
            self.orchestrator.rollback(
                domain="commercial",
                rollback_run_id="run_rb_fail",
                bad_run_id="run_actual",
                target_run_id="run_inventado"
            )

    def test_cp16_loss_of_lock_ownership(self):
        """CP-16: Pérdida de propiedad del lock durante renew_lease; retorna False."""
        mock_job = MagicMock()
        mock_job.num_dml_affected_rows = 0 # 0 filas afectadas = lock robado o expirado
        self.mock_client.query.return_value = mock_job

        renewed = self.orchestrator.renew_lease("commercial", "run_lost_lock", fencing_token=99)
        self.assertFalse(renewed)

    def test_cp17_retry_after_concurrency_conflict(self):
        """CP-17: Reintento exitoso tras error transitorio 503 ServiceUnavailable."""
        mock_transient = ServiceUnavailable("503 Backend temporary error")
        mock_ok = MagicMock()
        mock_ok.result.return_value = []

        self.mock_client.query.side_effect = [mock_transient, mock_ok]

        with patch("time.sleep", return_value=None):
            res = self.orchestrator.execute_bq_with_retry(
                sql="SELECT 1",
                params=[],
                step_name="TEST_RETRY",
                domain="commercial",
                run_id="run_retry_ok",
                max_retries=3,
                initial_wait=1.0
            )
            self.assertIsNotNone(res)
            self.assertEqual(self.mock_client.query.call_count, 2)

if __name__ == "__main__":
    unittest.main()
