-- =====================================================================
-- 13_audit.sql
-- MediCore HCMS - Audit log usage (report queries, no DDL).
-- AUDIT_LOG is filled automatically by trg_bill_audit, trg_patient_audit,
-- trg_appointment_audit and trg_medicine_stock_audit (10_triggers.sql).
-- user_id is resolved from the Oracle login via current_app_user_id, so
-- "who changed this patient's phone number?" has a real answer.
-- =====================================================================

-- Latest 20 changes, with the application user who made them
SELECT al.audit_id, al.table_name, al.operation, al.record_id,
       NVL(u.username, '(schema owner)') AS changed_by, u.role_name,
       al.old_value, al.new_value, al.action_timestamp
FROM audit_log al
LEFT JOIN app_user u ON u.user_id = al.user_id
ORDER BY al.action_timestamp DESC
FETCH FIRST 20 ROWS ONLY;

-- Changes per user and table (GROUP BY on the audit trail)
SELECT NVL(u.username, '(schema owner)') AS changed_by, al.table_name, al.operation, COUNT(*) AS changes
FROM audit_log al
LEFT JOIN app_user u ON u.user_id = al.user_id
GROUP BY NVL(u.username, '(schema owner)'), al.table_name, al.operation
ORDER BY changes DESC;
