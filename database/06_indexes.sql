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
-- Disease/condition lookups for epidemiological reports (FK to DISEASE)
CREATE INDEX idx_diagnosis_disease ON diagnosis(disease_code);
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

-- =====================================================================
-- v2 additions
-- =====================================================================

-- (1) Foreign-key indexes. Oracle does NOT index FK columns automatically.
--     Without them, a DELETE/UPDATE of a parent key must full-scan the child
--     table and takes a table-level lock on it (a classic concurrency
--     problem), and every "all bills of patient X" join is a full scan.
CREATE INDEX idx_admission_patient   ON admission(patient_id);
CREATE INDEX idx_admission_bed       ON admission(room_bed_id);
CREATE INDEX idx_diagnosis_patient   ON diagnosis(patient_id);
CREATE INDEX idx_diagnosis_appt      ON diagnosis(appointment_id);
CREATE INDEX idx_vital_patient       ON vital_sign(patient_id);
CREATE INDEX idx_note_patient        ON clinical_note(patient_id);
CREATE INDEX idx_presc_patient       ON prescription(patient_id);
CREATE INDEX idx_laborder_patient    ON lab_order(patient_id);
CREATE INDEX idx_bill_patient        ON bill(patient_id);
CREATE INDEX idx_bill_appt           ON bill(appointment_id);
CREATE INDEX idx_billitem_bill       ON bill_item(bill_id);
CREATE INDEX idx_payment_bill        ON payment(bill_id);
CREATE INDEX idx_queue_patient       ON service_queue(patient_id);
CREATE INDEX idx_ml_pred_run         ON ml_prediction(run_id);
-- Not needed - already the LEADING columns of a UNIQUE / PRIMARY KEY index:
--   appointment(patient_id, appt_date)   <- uq_patient_timeslot (patient_id, appt_date, appt_time)
--                                           (this is what makes the ML feature sub-queries fast)
--   prescription_item(prescription_id)   <- uq_presc_medicine
--   diagnosis_symptom(diagnosis_id)      <- pk_diag_symptom
--   ml_prediction(appointment_id)        <- uq_ml_appt_run
-- (By the same leading-column rule idx_appt_doctor_date above is redundant
--  with uq_doctor_timeslot; it is kept only as a teaching example.)

-- (2) Function-based index: case-insensitive patient search
--     WHERE UPPER(last_name) LIKE UPPER(:q) || '%'   can use this index,
--     a plain index on last_name cannot be used once UPPER() wraps it.
CREATE INDEX idx_patient_upper_lname ON patient(UPPER(last_name));

-- (3) Date-range reporting on bills / payments
CREATE INDEX idx_bill_date           ON bill(bill_date);
CREATE INDEX idx_payment_date        ON payment(paid_date);

-- Try it (SQL Developer: F10 / "Explain Plan"):
--   EXPLAIN PLAN FOR SELECT * FROM patient WHERE UPPER(last_name) LIKE 'PAT%';
--   SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);   -- INDEX RANGE SCAN IDX_PATIENT_UPPER_LNAME
