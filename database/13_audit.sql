-- =====================================================================
-- 13_audit.sql
-- MediCore HCMS - Audit log usage.
-- The AUDIT_LOG table (01_schema.sql) is populated automatically by
-- trg_bill_audit and trg_patient_audit (10_triggers.sql) - this file is
-- just the demo/report query, not additional DDL.
--
-- Why audit logging matters here: clinical and billing records are
-- legally sensitive (analogous to HIPAA-style obligations); an audit
-- trail answers "who changed this patient's record, and what did it say
-- before?" - essential for both malpractice defense and detecting
-- unauthorized access.
-- =====================================================================
SELECT audit_id, table_name, operation, record_id, old_value, new_value, action_timestamp
FROM audit_log
ORDER BY action_timestamp DESC
FETCH FIRST 20 ROWS ONLY;
