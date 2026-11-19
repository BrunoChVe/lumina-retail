-- SCRIPT 03d: WRITE PREDICTIVE
BEGIN
  DECLARE source_run STRING;
  SET source_run = (SELECT run_id FROM `lumina-retail-001.lumina_stage.model_evaluation_metrics` ORDER BY evaluated_at DESC LIMIT 1);

  BEGIN TRANSACTION;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_predictive_metrics` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_predictive_predictions` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` WHERE run_id = @run_id AND domain = "predictive" AND operation_type = "WRITE_TABLE";

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_predictive_metrics`
    SELECT @run_id, @publish_date, run_id, model_name, metric, value, target, split_start, split_end, n_test_rows, evaluated_at, evaluation_type
    FROM `lumina-retail-001.lumina_stage.model_evaluation_metrics` WHERE run_id = source_run;
    
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES (GENERATE_UUID(), @run_id, 1, "WRITE_TABLE", "predictive", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_predictive_metrics"));

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_predictive_predictions`
    SELECT @run_id, @publish_date, run_id, semana, categoria, actual, prediccion, error_absoluto
    FROM `lumina-retail-001.lumina_stage.model_evaluation_predictions` WHERE run_id = source_run;
    
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES (GENERATE_UUID(), @run_id, 2, "WRITE_TABLE", "predictive", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_predictive_predictions"));
  COMMIT TRANSACTION;
EXCEPTION WHEN ERROR THEN ROLLBACK TRANSACTION; RAISE USING MESSAGE = @@error.message;
END;
