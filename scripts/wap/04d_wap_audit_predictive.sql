-- SCRIPT 04d: AUDIT PREDICTIVE
BEGIN
  DELETE FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` WHERE run_id = @run_id AND domain = "predictive";

  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "predictive", @audit_timestamp, "TEST_PRED_METRICS_EXIST", (COUNT(*) > 0), TO_JSON_STRING(STRUCT(COUNT(*) AS count_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_predictive_metrics` WHERE run_id = @run_id;

  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "predictive", @audit_timestamp, "TEST_PRED_NO_NEGATIVE_PREDS", (COUNT(*) = 0), TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_predictive_predictions` WHERE run_id = @run_id AND prediccion < 0;
  
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "predictive", @audit_timestamp, "TEST_PRED_VALID_DATES", (COUNT(*) = 0), TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_predictive_predictions` WHERE run_id = @run_id AND semana IS NULL;
END;
