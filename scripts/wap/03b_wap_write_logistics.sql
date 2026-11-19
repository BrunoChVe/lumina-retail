-- SCRIPT 03b: WRITE LOGISTICS (ATÓMICO E IDEMPOTENTE)
-- Parámetros BQ: @run_id (STRING), @publish_date (TIMESTAMP), @operator (STRING), @fingerprint (STRING)

BEGIN
  BEGIN TRANSACTION;
    -- 1. LIMPIEZA IDEMPOTENTE
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` WHERE run_id = @run_id;
    DELETE FROM `lumina-retail-001.lumina_sandbox.gold_execution_history` 
    WHERE run_id = @run_id AND domain = "logistics" AND operation_type = "WRITE_TABLE";
    
    -- 2. MATERIALIZAR gold_logistics_dashboard (24 columnas)
    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_logistics_dashboard` (
      run_id, publish_date, source_system, source_label, order_cohort_month, total_orders,
      valid_shipments, valid_deliveries, deliveries_with_estimate, late_deliveries, valid_returns,
      invalid_shipping_sequence, invalid_delivery_sequence, delivery_without_shipment,
      future_shipments, future_deliveries, future_returns, avg_shipping_hours, avg_delivery_hours,
      shipment_coverage_pct, delivery_coverage_pct, late_delivery_rate_pct, late_delivery_data_status, calculated_at
    )
    SELECT 
      @run_id, @publish_date, source_system, source_label, order_cohort_month, total_orders, valid_shipments, valid_deliveries, deliveries_with_estimate, late_deliveries, valid_returns, invalid_shipping_sequence, invalid_delivery_sequence, delivery_without_shipment, future_shipments, future_deliveries, future_returns, avg_shipping_hours, avg_delivery_hours, shipment_coverage_pct, delivery_coverage_pct, late_delivery_rate_pct, late_delivery_data_status, calculated_at
    FROM `lumina-retail-001.lumina_stage.vw_logistics_dashboard_final_v1`
    WHERE source_system IN ("olist", "thelook") AND source_system != "uci";

    INSERT INTO `lumina-retail-001.lumina_sandbox.gold_execution_history` 
      (event_id, run_id, event_sequence, operation_type, domain, event_type, event_timestamp, operator, input_fingerprint, details)
    VALUES 
      (GENERATE_UUID(), @run_id, 1, "WRITE_TABLE", "logistics", "SUCCESS", CURRENT_TIMESTAMP(), @operator, @fingerprint, JSON_OBJECT("table_name", "gold_logistics_dashboard"));

  COMMIT TRANSACTION;
EXCEPTION WHEN ERROR THEN
  ROLLBACK TRANSACTION;
  RAISE USING MESSAGE = @@error.message;
END;
