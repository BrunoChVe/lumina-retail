-- SCRIPT 01b: INICIALIZACIÓN DML WAP ROBUSTA
-- Comprueba duplicados preexistentes, dominios desconocidos y garantiza idempotencia ante inicialización concurrente.

BEGIN
  -- 1. PREVALIDACIÓN DE INTEGRIDAD
  -- BigQuery no tiene restricciones UNIQUE reforzadas (NOT ENFORCED). 
  -- Se verifica que no existan duplicados ni dominios inválidos antes de inicializar.
  ASSERT (
    SELECT COUNT(*) = COUNT(DISTINCT domain) AND COUNTIF(domain NOT IN ("commercial", "logistics")) = 0
    FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
  ) AS "ABORT_INTEGRITY: gold_publisher_lock contiene dominios duplicados o desconocidos.";

  ASSERT (
    SELECT COUNT(*) = COUNT(DISTINCT domain) AND COUNTIF(domain NOT IN ("commercial", "logistics")) = 0
    FROM `lumina-retail-001.lumina_sandbox.gold_release_control`
  ) AS "ABORT_INTEGRITY: gold_release_control contiene dominios duplicados o desconocidos.";

  -- 2. INICIALIZACIÓN ATÓMICA DE gold_publisher_lock
  -- Si dos orquestadores ejecutan MERGE concurrentemente sobre la tabla:
  -- BigQuery OCC abortará una de las transacciones con "concurrent update".
  -- Al reintentar, la condición ON T.domain = S.domain evaluará MATCHED y no duplicará filas.
  MERGE `lumina-retail-001.lumina_sandbox.gold_publisher_lock` T
  USING (
    SELECT "commercial" AS domain, "FREE" AS status, CAST(NULL AS STRING) AS locked_by_run_id, 0 AS fencing_token, CAST(NULL AS TIMESTAMP) AS leased_until, CAST(NULL AS TIMESTAMP) AS last_published_at
    UNION ALL
    SELECT "logistics" AS domain, "FREE" AS status, CAST(NULL AS STRING) AS locked_by_run_id, 0 AS fencing_token, CAST(NULL AS TIMESTAMP) AS leased_until, CAST(NULL AS TIMESTAMP) AS last_published_at
  ) S
  ON T.domain = S.domain
  WHEN NOT MATCHED THEN
    INSERT (domain, status, locked_by_run_id, fencing_token, leased_until, last_published_at)
    VALUES (S.domain, S.status, S.locked_by_run_id, S.fencing_token, S.leased_until, S.last_published_at);

  -- 3. INICIALIZACIÓN ATÓMICA DE gold_release_control
  MERGE `lumina-retail-001.lumina_sandbox.gold_release_control` T
  USING (
    SELECT "commercial" AS domain, CAST(NULL AS STRING) AS current_run_id, CAST(NULL AS STRING) AS previous_run_id, "EMPTY" AS status, CURRENT_TIMESTAMP() AS released_at
    UNION ALL
    SELECT "logistics" AS domain, CAST(NULL AS STRING) AS current_run_id, CAST(NULL AS STRING) AS previous_run_id, "EMPTY" AS status, CURRENT_TIMESTAMP() AS released_at
  ) S
  ON T.domain = S.domain
  WHEN NOT MATCHED THEN
    INSERT (domain, current_run_id, previous_run_id, status, released_at)
    VALUES (S.domain, S.current_run_id, S.previous_run_id, S.status, S.released_at);

  -- 4. POSTVALIDACIÓN DE CARDINALIDAD EXACTA (Exactamente 2 filas por tabla, 1 por dominio)
  ASSERT (
    SELECT COUNT(*) = 2 AND COUNT(DISTINCT domain) = 2
    FROM `lumina-retail-001.lumina_sandbox.gold_publisher_lock`
  ) AS "ABORT_INTEGRITY: gold_publisher_lock no contiene exactamente 2 filas tras la inicialización.";

  ASSERT (
    SELECT COUNT(*) = 2 AND COUNT(DISTINCT domain) = 2
    FROM `lumina-retail-001.lumina_sandbox.gold_release_control`
  ) AS "ABORT_INTEGRITY: gold_release_control no contiene exactamente 2 filas tras la inicialización.";
END;
