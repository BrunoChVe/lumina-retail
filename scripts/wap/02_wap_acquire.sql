-- SCRIPT 02: ADQUISICIÓN Y RENOVACIÓN CONDICIONAL DEL LOCK
-- Inyección: @domain (STRING), @run_id (STRING)

BEGIN
  -- 1. Validar dominio permitido
  ASSERT @domain IN ("commercial", "logistics", "inventory", "predictive") 
    AS "ABORT_BUSINESS: Dominio no reconocido. Solo se admiten commercial y logistics.";

  -- 2. Adquisición atómica (Nueva o Robo de lease expirado) o Re-entrada idempotente del mismo run_id
  UPDATE `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
  SET 
    status = "LOCKED",
    locked_by_run_id = @run_id,
    -- Si es re-entrada del mismo run_id conserva el token; si es nueva adquisición o robo lo incrementa
    fencing_token = IF(locked_by_run_id = @run_id AND status = "LOCKED" AND leased_until >= CURRENT_TIMESTAMP(), fencing_token, fencing_token + 1),
    leased_until = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
  WHERE domain = @domain 
    AND (
      status = "FREE" 
      OR leased_until < CURRENT_TIMESTAMP() 
      OR (status = "LOCKED" AND locked_by_run_id = @run_id)
    );

  -- 3. Verificación inmediata de afectación
  IF @@row_count != 1 THEN
    RAISE USING MESSAGE = "ABORT_OCC: LOCK_NOT_ACQUIRED. El lock está ocupado por otro proceso con lease vigente.";
  END IF;

  -- 4. Recuperación del token asignado para captura por el orquestador
  SELECT fencing_token 
  FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
  WHERE domain = @domain AND status = "LOCKED" AND locked_by_run_id = @run_id;
END;
