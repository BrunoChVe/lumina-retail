-- SCRIPT 04c: AUDIT INVENTORY
BEGIN
  DELETE FROM `lumina-retail-001.lumina_sandbox.gold_audit_results` WHERE run_id = @run_id AND domain = "inventory";

  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "inventory", @audit_timestamp, "TEST_INV_PK_NOT_NULL", (COUNT(*) = 0), TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_inventory_current` WHERE run_id = @run_id AND (product_id IS NULL OR region IS NULL);

  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "inventory", @audit_timestamp, "TEST_INV_NO_CYBER_TEST", (COUNT(*) = 0), TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_inventory_current` WHERE run_id = @run_id AND region = "CYBER_TEST";
  
  INSERT INTO `lumina-retail-001.lumina_sandbox.gold_audit_results`
  SELECT GENERATE_UUID(), @run_id, "inventory", @audit_timestamp, "TEST_INV_NO_NEGATIVE_STOCK", (COUNT(*) = 0), TO_JSON_STRING(STRUCT(COUNT(*) AS failed_rows, @catalog_version AS cat))
  FROM `lumina-retail-001.lumina_sandbox.gold_inventory_current` WHERE run_id = @run_id AND stock_registrado < 0;
END;
