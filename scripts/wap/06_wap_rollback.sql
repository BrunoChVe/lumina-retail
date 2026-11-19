-- SCRIPT 06: ROLLBACK ATÓMICO Y COORDINADO
-- Inyección: @domain (STRING), @rollback_run_id (STRING), @bad_run_id (STRING), @target_run_id (STRING),
--             @mandatory_tests (ARRAY<STRING>), @mandatory_tables (ARRAY<STRING>)

BEGIN
  -- Validar dominio
  ASSERT @domain IN ("commercial", "logistics", "inventory", "predictive") 
    AS "ABORT_BUSINESS: Dominio no reconocido para rollback.";

  -- 1. ADQUIRIR LOCK CONDICIONALMENTE PARA ROLLBACK
  UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
  SET status = "LOCKED", 
      locked_by_run_id = @rollback_run_id, 
      fencing_token = fencing_token + 1, 
      leased_until = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 10 MINUTE)
  WHERE domain = @domain 
    AND (status = "FREE" OR leased_until < CURRENT_TIMESTAMP());

  IF @@row_count != 1 THEN 
    RAISE USING MESSAGE = "ABORT_OCC: Lock ocupado. Imposible iniciar rollback concurrente."; 
  END IF;

  -- 2. CAPTURAR EL TOKEN ASIGNADO AL ROLLBACK
  DECLARE v_token INT64;
  SET v_token = (
    SELECT fencing_token 
    FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock` 
    WHERE domain = @domain AND locked_by_run_id = @rollback_run_id AND status = "LOCKED"
  );

  BEGIN TRANSACTION;

    -- 3. VALIDAR QUE CURRENT_RUN_ID SIGUE SIENDO EL BAD_RUN_ID (Protección anti-sobrescritura)
    ASSERT (
      SELECT current_run_id = @bad_run_id 
      FROM `lumina-retail-001.lumina_sandbox.gold_release_control` 
      WHERE domain = @domain
    ) AS "ABORT_BUSINESS: El current_run_id actual ya no coincide con bad_run_id. Rollback abortado.";
    
    -- 4. VALIDAR QUE EL TARGET_RUN_ID CORRESPONDE A UNA PUBLICACIÓN PREVIA EXITOSA
    ASSERT (
      SELECT COUNT(*) = 1 
      FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      WHERE run_id = @target_run_id 
        AND domain = @domain 
        AND operation_type = "PUBLISH" 
        AND event_type = "SUCCESS"
    ) AS "ABORT_BUSINESS: El target_run_id no es un release publicado válido.";

    -- 5. VALIDAR MANIFIESTO DEL TARGET_RUN_ID
    ASSERT (
      WITH expected AS (SELECT tbl FROM UNNEST(@mandatory_tables) AS tbl),
           actual AS (
             SELECT JSON_VALUE(details, "$.table_name") AS tbl 
             FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
             WHERE run_id = @target_run_id AND domain = @domain AND operation_type = "WRITE_TABLE" AND event_type = "SUCCESS"
           ),
      missing_tbl AS (
        SELECT tbl FROM expected EXCEPT DISTINCT SELECT tbl FROM actual
      ),
      unexpected_tbl AS (
        SELECT tbl FROM actual EXCEPT DISTINCT SELECT tbl FROM expected
      )
      SELECT (SELECT COUNT(*) FROM missing_tbl) = 0
         AND (SELECT COUNT(*) FROM unexpected_tbl) = 0
    ) AS "ABORT_BUSINESS: Tablas del target_run_id incompletas.";

    -- 6. VALIDAR AUDITORÍAS DEL TARGET_RUN_ID
    ASSERT (
      WITH expected AS (SELECT t FROM UNNEST(@mandatory_tests) AS t),
           actual AS (
             SELECT test_name 
             FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` 
             WHERE run_id = @target_run_id AND domain = @domain AND passed = TRUE
           ),
      missing_test AS (
        SELECT t FROM expected EXCEPT DISTINCT SELECT test_name FROM actual
      ),
      unexpected_test AS (
        SELECT test_name FROM actual EXCEPT DISTINCT SELECT t FROM expected
      )
      SELECT (SELECT COUNT(*) FROM missing_test) = 0
         AND (SELECT COUNT(*) FROM unexpected_test) = 0
    ) AS "ABORT_BUSINESS: Auditorías del target_run_id incompletas.";

    -- 7. RENOVAR LEASE DENTRO DE LA TRANSACCIÓN
    UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock` 
    SET leased_until = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE) 
    WHERE domain = @domain 
      AND status = "LOCKED" 
      AND locked_by_run_id = @rollback_run_id 
      AND fencing_token = v_token 
      AND leased_until >= CURRENT_TIMESTAMP();

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_OCC: Lease expirado durante rollback."; 
    END IF;

    -- 8. ACTUALIZAR RELEASE_CONTROL (Restaurar puntero anterior)
    UPDATE `lumina-retail-001.lumina_sandbox.gold_release_control`
    SET previous_run_id = current_run_id, 
        current_run_id = @target_run_id, 
        released_at = CURRENT_TIMESTAMP()
    WHERE domain = @domain 
      AND current_run_id = @bad_run_id;

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_BUSINESS: Conflicto en release_control durante rollback."; 
    END IF;

    -- 9. REGISTRAR EVENTO ROLLBACK SUCCESS
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, details)
    VALUES 
      (GENERATE_UUID(), @rollback_run_id, 1, "ROLLBACK", @domain, "SUCCESS", CURRENT_TIMESTAMP(), SESSION_USER(), 
       JSON_OBJECT("reverted_run_id", @bad_run_id, "restored_run_id", @target_run_id));

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_BUSINESS: Error al registrar evento en execution_history."; 
    END IF;

    -- 10. LIBERAR LOCK CONDICIONALMENTE
    UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
    SET status = "FREE", 
        locked_by_run_id = NULL, 
        last_published_at = CURRENT_TIMESTAMP()
    WHERE domain = @domain 
      AND status = "LOCKED" 
      AND locked_by_run_id = @rollback_run_id 
      AND fencing_token = v_token;

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_OCC: Error al liberar lock de rollback."; 
    END IF;

  COMMIT TRANSACTION;

EXCEPTION WHEN ERROR THEN
  ROLLBACK TRANSACTION;
  -- Recuperación segura del lock: liberar fuera de la transacción para no dejar bloqueado el dominio
  UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock` 
  SET status = "FREE", locked_by_run_id = NULL 
  WHERE domain = @domain AND locked_by_run_id = @rollback_run_id AND fencing_token = v_token;
  
  RAISE USING MESSAGE = @@error.message;
END;
