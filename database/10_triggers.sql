-- =====================================================================
-- 10_triggers.sql
-- MediCore HCMS - Row-level triggers enforcing business rules at the DB
-- tier. Run AFTER schema/data (and after 07/08/09 since some triggers
-- reference tables only, not procedures, so order vs 07-09 doesn't matter,
-- but this must run after 01_schema.sql).
-- =====================================================================
-- trg_appointment_conflict
-- A doctor cannot have two overlapping appointments. BEFORE INSERT/UPDATE,
-- row-level. The UNIQUE (doctor_id, appt_date, appt_time) constraint from
-- 01_schema.sql already blocks exact duplicates; this trigger is kept to
-- show the pattern and allow future extension to overlapping duration
-- ranges (which a simple UNIQUE constraint cannot express).
-- NOTE: INSERT only. A row-level trigger that queries its own table raises
-- ORA-04091 (mutating table) on UPDATE, which would break e.g. marking an
-- appointment COMPLETED. The UNIQUE constraints already cover UPDATEs.
CREATE OR REPLACE TRIGGER trg_appointment_conflict
BEFORE INSERT ON appointment
FOR EACH ROW
DECLARE
    v_conflict_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_conflict_count
    FROM appointment
    WHERE doctor_id = :NEW.doctor_id
      AND appt_date = :NEW.appt_date
      AND appt_time = :NEW.appt_time
      AND status NOT IN ('CANCELLED')
      AND appointment_id != NVL(:NEW.appointment_id, -1);
    IF v_conflict_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20010, 'Doctor already has an appointment at this date/time.');
    END IF;
END;
/
-- trg_prescription_stock_check
-- Cannot prescribe more units than are in stock. BEFORE INSERT, row-level.
CREATE OR REPLACE TRIGGER trg_prescription_stock_check
BEFORE INSERT ON prescription_item
FOR EACH ROW
DECLARE
    v_stock NUMBER;
BEGIN
    SELECT stock_quantity INTO v_stock FROM medicine WHERE medicine_id = :NEW.medicine_id;
    IF :NEW.quantity > v_stock THEN
        RAISE_APPLICATION_ERROR(-20011, 'Prescribed quantity exceeds available stock.');
    END IF;
END;
/
-- trg_inventory_deduct
-- Stock decreases automatically once a prescription item is recorded
-- (fulfilled at write time, in this simplified model). AFTER INSERT,
-- row-level. Only touches `medicine`, never `prescription_item` itself,
-- so it cannot hit ORA-04091 (mutating table).
CREATE OR REPLACE TRIGGER trg_inventory_deduct
AFTER INSERT ON prescription_item
FOR EACH ROW
BEGIN
    UPDATE medicine SET stock_quantity = stock_quantity - :NEW.quantity
    WHERE medicine_id = :NEW.medicine_id;
END;
/
-- trg_bill_audit
-- Every modification to a bill is logged. AFTER UPDATE, row-level.
CREATE OR REPLACE TRIGGER trg_bill_audit
AFTER UPDATE ON bill
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, operation, old_value, new_value)
    VALUES ('BILL', :OLD.bill_id, 'UPDATE',
            'status=' || :OLD.status,
            'status=' || :NEW.status);
END;
/
-- trg_patient_audit
-- Tracks edits to sensitive patient fields. AFTER UPDATE, row-level. The
-- WHEN clause fires only when a sensitive field actually changed, avoiding
-- audit-log noise on no-op updates.
CREATE OR REPLACE TRIGGER trg_patient_audit
AFTER UPDATE ON patient
FOR EACH ROW
WHEN (NVL(OLD.phone,'x') != NVL(NEW.phone,'x')
   OR NVL(OLD.address,'x') != NVL(NEW.address,'x')
   OR NVL(OLD.blood_group,'x') != NVL(NEW.blood_group,'x'))
BEGIN
    INSERT INTO audit_log (table_name, record_id, operation, old_value, new_value)
    VALUES ('PATIENT', :OLD.patient_id, 'UPDATE',
            'phone=' || :OLD.phone || ',addr=' || :OLD.address || ',bg=' || :OLD.blood_group,
            'phone=' || :NEW.phone || ',addr=' || :NEW.address || ',bg=' || :NEW.blood_group);
END;
/
-- trg_bed_status_update
-- Bed availability flips automatically on admission/discharge. AFTER
-- INSERT OR UPDATE, row-level.
CREATE OR REPLACE TRIGGER trg_bed_status_update
AFTER INSERT OR UPDATE ON admission
FOR EACH ROW
BEGIN
    IF INSERTING OR (:NEW.status = 'ADMITTED' AND :OLD.status IS NULL) THEN
        UPDATE room_bed SET status = 'OCCUPIED' WHERE room_bed_id = :NEW.room_bed_id;
    ELSIF UPDATING AND :NEW.status = 'DISCHARGED' AND :OLD.status = 'ADMITTED' THEN
        UPDATE room_bed SET status = 'AVAILABLE' WHERE room_bed_id = :NEW.room_bed_id;
    END IF;
END;
/
-- Trigger limitations (for viva): triggers cannot query the table they fire
-- on within the same statement without a mutating-table error (ORA-04091)
-- unless the read is scoped correctly (as engineered above, by only
-- touching other tables); row-level triggers also execute per-row, which
-- can be a performance concern for bulk loads (04b_bulk_data.sql uses a
-- small FOR loop of 200, not a 10,000-row bulk load, to keep row-trigger
-- overhead trivial for a class demo).
