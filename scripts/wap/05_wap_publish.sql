-- SCRIPT 05: PUBLISH ATÓMICO Y TRANSACCIONAL
-- Inyección: @domain (STRING), @run_id (STRING), @mem_fencing_token (INT64), @expected_previous_run_id (STRING),
--             @catalog_version (STRING), @mandatory_tests (ARRAY<STRING>), @mandatory_tables (ARRAY<STRING>), @seq_publish (INT64)

BEGIN
  -- Validar dominio
  ASSERT @domain IN ("commercial", "logistics", "inventory", "predictive") 
    AS "ABORT_BUSINESS: Dominio no reconocido.";

  BEGIN TRANSACTION;

    -- 1. VALIDACIÓN SIMÉTRICA Y SIN DUPLICADOS DEL CATÁLOGO DE AUDITORÍAS
    ASSERT (
      WITH expected AS (
        SELECT t FROM UNNEST(@mandatory_tests) AS t
      ),
      actual AS (
        SELECT test_name, passed 
        FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` 
        WHERE run_id = @run_id 
          AND domain = @domain 
          AND JSON_VALUE(details, "$.cat") = @catalog_version
      ),
      missing AS (
        SELECT t FROM expected EXCEPT DISTINCT SELECT test_name FROM actual WHERE passed IS TRUE
      ),
      unexpected AS (
        SELECT test_name FROM actual EXCEPT DISTINCT SELECT t FROM expected
      ),
      duplicates AS (
        SELECT test_name FROM actual GROUP BY test_name HAVING COUNT(*) > 1
      ),
      failures AS (
        SELECT test_name FROM actual WHERE passed IS NOT TRUE
      )
      SELECT (SELECT COUNT(*) FROM missing) = 0
         AND (SELECT COUNT(*) FROM unexpected) = 0
         AND (SELECT COUNT(*) FROM duplicates) = 0
         AND (SELECT COUNT(*) FROM failures) = 0
    ) AS "ABORT_BUSINESS: Catálogo de auditorías incompleto, alterado, con duplicados o fallos.";

    -- 2. VALIDACIÓN SIMÉTRICA Y SIN DUPLICADOS DEL MANIFIESTO DE TABLAS GOLD
    ASSERT (
      WITH expected AS (
        SELECT tbl FROM UNNEST(@mandatory_tables) AS tbl
      ),
      actual AS (
        SELECT JSON_VALUE(details, "$.table_name") AS tbl 
        FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
        WHERE run_id = @run_id 
          AND domain = @domain 
          AND operation_type = "WRITE_TABLE" 
          AND event_type = "SUCCESS"
      ),
      missing AS (
        SELECT tbl FROM expected EXCEPT DISTINCT SELECT tbl FROM actual
      ),
      unexpected AS (
        SELECT tbl FROM actual EXCEPT DISTINCT SELECT tbl FROM expected
      ),
      duplicates AS (
        SELECT tbl FROM actual GROUP BY tbl HAVING COUNT(*) > 1
      ),
      failures AS (
        SELECT JSON_VALUE(details, "$.table_name") AS tbl 
        FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
        WHERE run_id = @run_id 
          AND domain = @domain 
          AND operation_type = "WRITE_TABLE" 
          AND event_type = "FAILURE"
      )
      SELECT (SELECT COUNT(*) FROM missing) = 0
         AND (SELECT COUNT(*) FROM unexpected) = 0
         AND (SELECT COUNT(*) FROM duplicates) = 0
         AND (SELECT COUNT(*) FROM failures) = 0
    ) AS "ABORT_BUSINESS: Manifiesto de tablas incompleto, con fallos o duplicados.";

    -- 3. RENOVAR LEASE DENTRO DE LA TRANSACCIÓN (Comprueba fencing_token y vigencia)
    UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
    SET leased_until = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
    WHERE domain = @domain 
      AND status = "LOCKED" 
      AND locked_by_run_id = @run_id 
      AND fencing_token = @mem_fencing_token 
      AND leased_until >= CURRENT_TIMESTAMP();

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_OCC: Fallo en renovación de lease. Lock robado, expirado o ABA obsoleto."; 
    END IF;

    -- 4. ACTUALIZAR PUNTERO DE RELEASE CONTROL (Condicional sobre versión previa esperada)
    UPDATE `lumina-retail-001.lumina_sandbox.gold_release_control`
    SET previous_run_id = current_run_id, 
        current_run_id = @run_id, 
        status = "PUBLISHED", 
        released_at = CURRENT_TIMESTAMP()
    WHERE domain = @domain 
      AND (
        current_run_id = @expected_previous_run_id 
        OR (@expected_previous_run_id IS NULL AND current_run_id IS NULL)
      );

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_BUSINESS: Conflicto en release_control. La versión actual en base de datos no coincide con la esperada."; 
    END IF;

    -- 5. LIBERAR LOCK CONDICIONALMENTE (Solo el propietario con fencing_token válido puede liberar)
    UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
    SET status = "FREE", 
        locked_by_run_id = NULL, 
        last_published_at = CURRENT_TIMESTAMP()
    WHERE domain = @domain 
      AND status = "LOCKED" 
      AND locked_by_run_id = @run_id 
      AND fencing_token = @mem_fencing_token;

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_OCC: Error interno al liberar el lock tras publicar."; 
    END IF;

    -- 6. REGISTRAR EVENTO PUBLISH SUCCESS
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, details)
    VALUES 
      (GENERATE_UUID(), @run_id, @seq_publish, "PUBLISH", @domain, "SUCCESS", CURRENT_TIMESTAMP(), SESSION_USER(), 
       JSON_OBJECT("previous_run_id", @expected_previous_run_id, "fencing_token", @mem_fencing_token));

    IF @@row_count != 1 THEN 
      RAISE USING MESSAGE = "ABORT_BUSINESS: Fallo en inserción de bitácora de publicación."; 
    END IF;

  COMMIT TRANSACTION;

EXCEPTION WHEN ERROR THEN
  ROLLBACK TRANSACTION;
  RAISE USING MESSAGE = @@error.message;
END;
