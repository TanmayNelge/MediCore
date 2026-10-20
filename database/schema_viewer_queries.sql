-- =====================================================================
-- schema_viewer_queries.sql
-- MediCore HCMS - Queries powering frontend pages (Phase 13.2, 14.2, 14.3).
-- These read Oracle's own data dictionary so the "VIEW DATABASE SCHEMA"
-- page never drifts from the real schema - no hardcoded table/column list.
-- =====================================================================

-- 13.2 Dashboard KPIs - powers the dashboard cards in one round trip
SELECT
  (SELECT COUNT(*) FROM patient) AS total_patients,
  (SELECT COUNT(*) FROM appointment WHERE appt_date = TRUNC(SYSDATE)) AS todays_appointments,
  (SELECT COUNT(*) FROM service_queue WHERE status='WAITING' AND queue_date=TRUNC(SYSDATE)) AS current_queue,
  (SELECT COUNT(*) FROM room_bed WHERE status='AVAILABLE') AS available_beds,
  (SELECT COUNT(*) FROM lab_order WHERE status IN ('ORDERED','SAMPLE_COLLECTED')) AS pending_labs,
  (SELECT NVL(SUM(amount_paid),0) FROM payment WHERE paid_date=TRUNC(SYSDATE)) AS revenue_today
FROM dual;

-- 14.2 "VIEW DATABASE SCHEMA" - table/column list with PK/FK badges,
-- fetched live from Oracle's data dictionary
SELECT table_name, column_name, data_type, nullable,
       (SELECT 'PK' FROM user_cons_columns ucc JOIN user_constraints uc
          ON uc.constraint_name = ucc.constraint_name
        WHERE uc.constraint_type='P' AND ucc.table_name = utc.table_name
          AND ucc.column_name = utc.column_name AND ROWNUM=1) AS is_pk,
       (SELECT 'FK' FROM user_cons_columns ucc JOIN user_constraints uc
          ON uc.constraint_name = ucc.constraint_name
        WHERE uc.constraint_type='R' AND ucc.table_name = utc.table_name
          AND ucc.column_name = utc.column_name AND ROWNUM=1) AS is_fk
FROM user_tab_columns utc
ORDER BY table_name, column_id;

-- 14.3 Relationship lines from foreign keys - draws the FK arrows on the
-- schema viewer automatically, keeping it synchronized with 01_schema.sql
SELECT a.table_name AS child_table, a.column_name AS fk_column,
       c_pk.table_name AS parent_table
FROM user_cons_columns a
JOIN user_constraints c ON a.constraint_name = c.constraint_name
JOIN user_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name
WHERE c.constraint_type = 'R';
