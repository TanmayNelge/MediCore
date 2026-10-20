-- =====================================================================
-- 06_indexes.sql
-- MediCore HCMS - Supporting indexes. Run AFTER 01_schema.sql.
-- =====================================================================
-- Patient lookup by phone/email is extremely common at reception
CREATE INDEX idx_patient_phone ON patient(phone);
-- idx_patient_email is commented out: the UNIQUE constraint on patient.email
-- already auto-creates a unique index in Oracle; running this would raise
-- ORA-01408 (column list already indexed). Uncomment only if the UNIQUE
-- constraint was dropped.
-- CREATE UNIQUE INDEX idx_patient_email ON patient(email);
-- Appointment scheduling queries filter heavily by date, and by doctor+date
CREATE INDEX idx_appt_date ON appointment(appt_date);
CREATE INDEX idx_appt_doctor_date ON appointment(doctor_id, appt_date);
-- Disease/condition lookups for epidemiological reports
CREATE INDEX idx_diagnosis_disease ON diagnosis(disease_name);
-- Lab report status is filtered constantly by the pending-reports view
CREATE INDEX idx_laborder_status ON lab_order(status);
-- Appointment status filter (e.g. WHERE status = 'NO_SHOW' for ML extraction)
CREATE INDEX idx_appt_status ON appointment(status);
-- Queue is polled continuously by type+status
CREATE INDEX idx_queue_type_status ON service_queue(queue_type, status);
-- Deliberately NOT indexed:
--   patient.gender, patient.blood_group  -- low cardinality (2-8 distinct
--     values); a B-tree index rarely beats a full scan and just adds write
--     overhead.
--   bill_item.item_description           -- free text, rarely filtered
--     exactly; would need a full-text index, out of scope.
--   audit_log.old_value / new_value (CLOB) -- CLOBs aren't practically
--     B-tree indexable, and the audit log is write-heavy/append-only.
--
-- idx_appt_doctor_date is a composite index: effective for "this doctor's
-- appointments on this date" and also serves date-only queries only if
-- doctor_id is a prefix match (leading-column rule).
