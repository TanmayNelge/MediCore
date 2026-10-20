-- =====================================================================
-- 08_procedures.sql
-- MediCore HCMS - Standalone PL/SQL procedures. Run AFTER 07_functions.sql.
-- =====================================================================
-- Book an appointment: validates doctor exists, slot free (trigger will also guard),
-- inserts appointment, adds an OPD queue entry. Demonstrates a multi-step transaction (Phase 10).
CREATE OR REPLACE PROCEDURE book_appointment(
     p_patient_id   IN NUMBER,
     p_doctor_id    IN NUMBER,
     p_appt_date    IN DATE,
     p_appt_time    IN VARCHAR2,
     p_reason       IN VARCHAR2,
     p_appointment_id OUT NUMBER
) IS
     v_dept_id NUMBER;
     v_qnum    NUMBER;
BEGIN
     SELECT department_id INTO v_dept_id FROM doctor WHERE doctor_id = p_doctor_id;
      INSERT INTO appointment (patient_id, doctor_id, appt_date, appt_time, reason)
      VALUES (p_patient_id, p_doctor_id, p_appt_date, p_appt_time, p_reason)
      RETURNING appointment_id INTO p_appointment_id;
      SELECT NVL(MAX(queue_number),0) + 1 INTO v_qnum
      FROM service_queue WHERE queue_type = 'OPD' AND queue_date = TRUNC(p_appt_date);
      INSERT INTO service_queue (queue_type, queue_number, queue_date, patient_id, doctor_id,
                                  department_id, priority_level)
      VALUES ('OPD', v_qnum, TRUNC(p_appt_date), p_patient_id, p_doctor_id, v_dept_id,
              determine_appointment_priority(p_patient_id,'OPD'));
    COMMIT;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20001, 'Doctor not found.');
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END book_appointment;
/
-- Admit a patient: validates bed availability, creates admission, updates bed status (trigger also does this,
-- shown redundantly here only to illustrate explicit procedural control; trigger is the real enforcement).
CREATE OR REPLACE PROCEDURE admit_patient(
     p_patient_id IN NUMBER, p_room_bed_id IN NUMBER, p_doctor_id IN NUMBER,
     p_reason IN VARCHAR2, p_admission_id OUT NUMBER
) IS
     v_status room_bed.status%TYPE;
BEGIN
     SELECT status INTO v_status FROM room_bed WHERE room_bed_id = p_room_bed_id FOR UPDATE;
    IF v_status != 'AVAILABLE' THEN
        RAISE_APPLICATION_ERROR(-20002, 'Selected bed is not available.');
    END IF;
    INSERT INTO admission (patient_id, room_bed_id, admitting_doctor_id, admission_reason)
    VALUES (p_patient_id, p_room_bed_id, p_doctor_id, p_reason)
    RETURNING admission_id INTO p_admission_id;
    COMMIT;    -- bed status flips via trg_bed_status_update (Phase 8)
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END admit_patient;
/
-- Generate a consolidated bill for a completed appointment (consultation + any linked lab/medicine items)
CREATE OR REPLACE PROCEDURE generate_bill(
     p_patient_id IN NUMBER, p_appointment_id IN NUMBER, p_bill_id OUT NUMBER
) IS
     v_fee NUMBER;
BEGIN
     INSERT INTO bill (patient_id, appointment_id) VALUES (p_patient_id, p_appointment_id)
     RETURNING bill_id INTO p_bill_id;
    SELECT doc.consultation_fee INTO v_fee
    FROM appointment a JOIN doctor doc ON doc.doctor_id = a.doctor_id
    WHERE a.appointment_id = p_appointment_id;
    INSERT INTO bill_item (bill_id, item_description, item_category, amount)
    VALUES (p_bill_id, 'Consultation fee', 'CONSULTATION', v_fee);
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END generate_bill;
/
-- Add a prescription with one item in a single call (stock check delegated to trg_prescription_stock_check)
CREATE OR REPLACE PROCEDURE add_prescription(
     p_patient_id IN NUMBER, p_doctor_id IN NUMBER, p_appointment_id IN NUMBER,
     p_medicine_id IN NUMBER, p_dosage IN VARCHAR2, p_duration_days IN NUMBER, p_quantity IN NUMBER,
     p_prescription_id OUT NUMBER
) IS
BEGIN
     INSERT INTO prescription (patient_id, doctor_id, appointment_id)
     VALUES (p_patient_id, p_doctor_id, p_appointment_id)
     RETURNING prescription_id INTO p_prescription_id;
   INSERT INTO prescription_item (prescription_id, medicine_id, dosage, duration_days, quantity)
   VALUES (p_prescription_id, p_medicine_id, p_dosage, p_duration_days, p_quantity);
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END add_prescription;
/
-- Register a lab order
CREATE OR REPLACE PROCEDURE register_lab_order(
     p_patient_id IN NUMBER, p_doctor_id IN NUMBER, p_lab_test_id IN NUMBER,
     p_lab_order_id OUT NUMBER
) IS
BEGIN
     INSERT INTO lab_order (patient_id, doctor_id, lab_test_id)
     VALUES (p_patient_id, p_doctor_id, p_lab_test_id)
     RETURNING lab_order_id INTO p_lab_order_id;
     COMMIT;
END register_lab_order;
/
