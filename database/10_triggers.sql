-- =====================================================================
-- 10_triggers.sql
-- MediCore HCMS - Triggers enforcing business rules at the DB tier.
-- Run AFTER 07_functions.sql and 08_procedures.sql (some triggers call
-- current_app_user_id / check_encounter_patient).
--
-- v2 changes
--   * trg_bed_status_update: an INSERT of an already-DISCHARGED admission no
--     longer marks the bed OCCUPIED; bed transfers (room_bed_id changes)
--     now free the old bed and occupy the new one.
--   * audit triggers record WHO changed the row (current_app_user_id) and
--     also cover DELETE.
--   * NEW trg_appointment_audit, trg_*_encounter_chk (5 consistency triggers),
--     trg_medicine_stock_audit.
-- =====================================================================

-- ---------------------------------------------------------------------
-- trg_appointment_conflict
-- A doctor cannot have two (non-cancelled) appointments in the same slot.
-- The UNIQUE (doctor_id, appt_date, appt_time) constraint already blocks
-- exact duplicates; this trigger shows the pattern and gives a readable
-- message. INSERT only: a row-level trigger that queries its own table
-- on UPDATE raises ORA-04091 (mutating table).
-- ---------------------------------------------------------------------
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
      AND status NOT IN ('CANCELLED');
    IF v_conflict_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20010, 'Doctor already has an appointment at this date/time.');
    END IF;
END;
/

-- ---------------------------------------------------------------------
-- trg_prescription_stock_check - cannot prescribe more than in stock.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_prescription_stock_check
BEFORE INSERT ON prescription_item
FOR EACH ROW
DECLARE
    v_stock NUMBER;
    v_name  medicine.medicine_name%TYPE;
BEGIN
    SELECT stock_quantity, medicine_name INTO v_stock, v_name FROM medicine WHERE medicine_id = :NEW.medicine_id;
    IF :NEW.quantity > v_stock THEN
        RAISE_APPLICATION_ERROR(-20011, 'Prescribed quantity (' || :NEW.quantity || ') of ' || v_name ||
                                        ' exceeds available stock (' || v_stock || ').');
    END IF;
END;
/

-- ---------------------------------------------------------------------
-- trg_inventory_deduct - stock decreases when a prescription item is
-- recorded. Touches MEDICINE only, never PRESCRIPTION_ITEM -> no ORA-04091.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_inventory_deduct
AFTER INSERT ON prescription_item
FOR EACH ROW
BEGIN
    UPDATE medicine SET stock_quantity = stock_quantity - :NEW.quantity
    WHERE medicine_id = :NEW.medicine_id;
END;
/

-- ---------------------------------------------------------------------
-- trg_bill_audit - every status change of a bill is logged.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_bill_audit
AFTER UPDATE OF status ON bill
FOR EACH ROW
WHEN (NVL(OLD.status, 'x') != NVL(NEW.status, 'x'))
BEGIN
    INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
    VALUES (current_app_user_id, 'BILL', :OLD.bill_id, 'UPDATE',
            'status=' || :OLD.status, 'status=' || :NEW.status);
END;
/

-- ---------------------------------------------------------------------
-- trg_patient_audit - sensitive patient fields (UPDATE) and deletions.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_patient_audit
AFTER UPDATE OR DELETE ON patient
FOR EACH ROW
BEGIN
    IF DELETING THEN
        INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
        VALUES (current_app_user_id, 'PATIENT', :OLD.patient_id, 'DELETE',
                'name=' || :OLD.first_name || ' ' || :OLD.last_name || ',phone=' || :OLD.phone, NULL);
    ELSIF NVL(:OLD.phone,'x') != NVL(:NEW.phone,'x')
       OR NVL(:OLD.address,'x') != NVL(:NEW.address,'x')
       OR NVL(:OLD.city,'x') != NVL(:NEW.city,'x')
       OR NVL(:OLD.blood_group,'x') != NVL(:NEW.blood_group,'x')
       OR NVL(:OLD.email,'x') != NVL(:NEW.email,'x')
       OR :OLD.first_name != :NEW.first_name OR :OLD.last_name != :NEW.last_name THEN
        INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
        VALUES (current_app_user_id, 'PATIENT', :OLD.patient_id, 'UPDATE',
                'name=' || :OLD.first_name || ' ' || :OLD.last_name || ',phone=' || :OLD.phone ||
                ',email=' || :OLD.email || ',addr=' || :OLD.address || ',' || :OLD.city || ',bg=' || :OLD.blood_group,
                'name=' || :NEW.first_name || ' ' || :NEW.last_name || ',phone=' || :NEW.phone ||
                ',email=' || :NEW.email || ',addr=' || :NEW.address || ',' || :NEW.city || ',bg=' || :NEW.blood_group);
    END IF;
END;
/

-- ---------------------------------------------------------------------
-- trg_appointment_audit - status changes, reschedules and deletes.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_appointment_audit
AFTER UPDATE OR DELETE ON appointment
FOR EACH ROW
BEGIN
    IF DELETING THEN
        INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
        VALUES (current_app_user_id, 'APPOINTMENT', :OLD.appointment_id, 'DELETE',
                'patient=' || :OLD.patient_id || ',doctor=' || :OLD.doctor_id || ',date=' ||
                TO_CHAR(:OLD.appt_date, 'YYYY-MM-DD') || ' ' || :OLD.appt_time || ',status=' || :OLD.status, NULL);
    ELSIF :OLD.status != :NEW.status OR :OLD.appt_date != :NEW.appt_date OR :OLD.appt_time != :NEW.appt_time THEN
        INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
        VALUES (current_app_user_id, 'APPOINTMENT', :OLD.appointment_id, 'UPDATE',
                'status=' || :OLD.status || ',slot=' || TO_CHAR(:OLD.appt_date, 'YYYY-MM-DD') || ' ' || :OLD.appt_time,
                'status=' || :NEW.status || ',slot=' || TO_CHAR(:NEW.appt_date, 'YYYY-MM-DD') || ' ' || :NEW.appt_time);
    END IF;
END;
/

-- ---------------------------------------------------------------------
-- trg_medicine_stock_audit - manual stock corrections are traceable.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_medicine_stock_audit
AFTER UPDATE OF stock_quantity ON medicine
FOR EACH ROW
WHEN (NEW.stock_quantity > OLD.stock_quantity)      -- restock / correction (deductions come from prescriptions)
BEGIN
    INSERT INTO audit_log (user_id, table_name, record_id, operation, old_value, new_value)
    VALUES (current_app_user_id, 'MEDICINE', :OLD.medicine_id, 'UPDATE',
            'stock=' || :OLD.stock_quantity, 'stock=' || :NEW.stock_quantity);
END;
/

-- ---------------------------------------------------------------------
-- trg_bed_status_update - bed availability follows admissions.
--   INSERT of an ADMITTED row            -> new bed OCCUPIED
--   ADMITTED -> DISCHARGED               -> bed AVAILABLE
--   room_bed_id changed (transfer_bed)   -> old bed AVAILABLE, new OCCUPIED
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_bed_status_update
AFTER INSERT OR UPDATE ON admission
FOR EACH ROW
BEGIN
    IF INSERTING THEN
        IF :NEW.status = 'ADMITTED' THEN
            UPDATE room_bed SET status = 'OCCUPIED' WHERE room_bed_id = :NEW.room_bed_id;
        END IF;
    ELSIF :NEW.status = 'DISCHARGED' AND :OLD.status = 'ADMITTED' THEN
        UPDATE room_bed SET status = 'AVAILABLE' WHERE room_bed_id = :OLD.room_bed_id;
    ELSIF :NEW.status = 'ADMITTED' AND :OLD.room_bed_id != :NEW.room_bed_id THEN
        UPDATE room_bed SET status = 'AVAILABLE' WHERE room_bed_id = :OLD.room_bed_id;
        UPDATE room_bed SET status = 'OCCUPIED'  WHERE room_bed_id = :NEW.room_bed_id;
    END IF;
END;
/

-- ---------------------------------------------------------------------
-- Encounter / patient consistency (5 small triggers, one shared procedure)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_diagnosis_encounter_chk
BEFORE INSERT OR UPDATE OF patient_id, appointment_id, admission_id ON diagnosis
FOR EACH ROW
BEGIN
    check_encounter_patient(:NEW.patient_id, :NEW.appointment_id, :NEW.admission_id, 'DIAGNOSIS');
END;
/
CREATE OR REPLACE TRIGGER trg_prescription_encounter_chk
BEFORE INSERT OR UPDATE OF patient_id, appointment_id ON prescription
FOR EACH ROW
BEGIN
    check_encounter_patient(:NEW.patient_id, :NEW.appointment_id, NULL, 'PRESCRIPTION');
END;
/
CREATE OR REPLACE TRIGGER trg_bill_encounter_chk
BEFORE INSERT OR UPDATE OF patient_id, appointment_id, admission_id ON bill
FOR EACH ROW
BEGIN
    check_encounter_patient(:NEW.patient_id, :NEW.appointment_id, :NEW.admission_id, 'BILL');
END;
/
CREATE OR REPLACE TRIGGER trg_vital_encounter_chk
BEFORE INSERT OR UPDATE OF patient_id, appointment_id, admission_id ON vital_sign
FOR EACH ROW
BEGIN
    check_encounter_patient(:NEW.patient_id, :NEW.appointment_id, :NEW.admission_id, 'VITAL_SIGN');
END;
/
CREATE OR REPLACE TRIGGER trg_note_encounter_chk
BEFORE INSERT OR UPDATE OF patient_id, appointment_id, admission_id ON clinical_note
FOR EACH ROW
BEGIN
    check_encounter_patient(:NEW.patient_id, :NEW.appointment_id, :NEW.admission_id, 'CLINICAL_NOTE');
END;
/

-- Trigger limitations (for viva): a row-level trigger cannot query the
-- table it fires on (ORA-04091 mutating table) - see 14_bill_status_trigger.sql
-- for the COMPOUND trigger work-around; row-level triggers run once per
-- row, which is why bulk loads (04_sample_data.sql) run BEFORE the
-- triggers are created, and reseed.py disables them while reloading.
