-- SCRIPT 03c: WRITE INVENTORY
BEGIN
  BEGIN TRANSACTION;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_inventory_current` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_inventory_risks` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` WHERE run_id = @run_id AND domain = "inventory" AND operation_type = "WRITE_TABLE";

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_inventory_current`
    SELECT @run_id, @publish_date, product_id, region, stock_registrado, fecha_ultimo_evento, fecha_procesamiento, minutos_desde_evento, estado_frescura,
      CASE WHEN stock_registrado < 10 THEN "CRITICO" WHEN stock_registrado <= 20 THEN "BAJO" ELSE "NORMAL" END AS estado_stock
    FROM `lumina-retail-001.lumina_streaming.stock_actual_vw`;
    
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES (GENERATE_UUID(), @run_id, 1, "WRITE_TABLE", "inventory", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_inventory_current"));

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_inventory_risks`
    SELECT @run_id, @publish_date, product_id, region, total_eventos, stock_promedio, stock_minimo, stock_maximo, alertas_criticas, eventos_stock_bajo, porcentaje_alertas
    FROM `lumina-retail-001.lumina_streaming.stock_risk_by_product_region`;
    
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES (GENERATE_UUID(), @run_id, 2, "WRITE_TABLE", "inventory", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_inventory_risks"));
  COMMIT TRANSACTION;
EXCEPTION WHEN ERROR THEN ROLLBACK TRANSACTION; RAISE USING MESSAGE = @@error.message;
END;
