-- =====================================================================
-- 08_procedures.sql
-- MediCore HCMS - Standalone PL/SQL procedures. Run AFTER 07_functions.sql.
--
-- Every procedure is ONE transaction: it either COMMITs all of its work or
-- ROLLBACKs all of it (Atomicity). Business-rule violations are reported
-- with RAISE_APPLICATION_ERROR(-200xx, '...') so the front end can show a
-- clear message.
--
-- Error code map
--   -20001 doctor not found            -20030 patient not found
--   -20002 bed not available           -20031 patient has dependent records
--   -20003 admission not found         -20032 appointment not found / not SCHEDULED
--   -20004 appointment date in past    -20033 slot already taken (reschedule)
--   -20005 invalid time format         -20040 payment > outstanding balance
--   -20006 patient not found (booking) -20041 bill not found / cancelled
--   -20050 encounter belongs to another patient (consistency triggers)
-- =====================================================================

-- ---------------------------------------------------------------------
-- book_appointment
-- Inserts the appointment AND its OPD queue token in one transaction.
-- Concurrency: queue_number = MAX()+1 is a classic race condition (two
-- receptionists booking at the same moment would both read MAX = 7 and
-- both try to insert token 8 -> ORA-00001). LOCK TABLE ... IN SHARE ROW
-- EXCLUSIVE MODE serialises token allocation for the few milliseconds the
-- transaction lasts; readers are never blocked (Oracle MVCC).
-- ---------------------------------------------------------------------
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
     v_dummy   NUMBER;
BEGIN
     IF TRUNC(p_appt_date) < TRUNC(SYSDATE) THEN
         RAISE_APPLICATION_ERROR(-20004, 'Appointment date cannot be in the past.');
     END IF;
     IF NOT REGEXP_LIKE(p_appt_time, '^([01][0-9]|2[0-3]):[0-5][0-9]$') THEN
         RAISE_APPLICATION_ERROR(-20005, 'Time must be in HH24:MI format, e.g. 09:30.');
     END IF;
     BEGIN
         SELECT 1 INTO v_dummy FROM patient WHERE patient_id = p_patient_id;
     EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20006, 'Patient ' || p_patient_id || ' does not exist.');
     END;
     BEGIN
         SELECT department_id INTO v_dept_id FROM doctor WHERE doctor_id = p_doctor_id;
     EXCEPTION WHEN NO_DATA_FOUND THEN
         RAISE_APPLICATION_ERROR(-20001, 'Doctor ' || p_doctor_id || ' does not exist.');
     END;

     INSERT INTO appointment (patient_id, doctor_id, appt_date, appt_time, reason)
     VALUES (p_patient_id, p_doctor_id, TRUNC(p_appt_date), p_appt_time, p_reason)
     RETURNING appointment_id INTO p_appointment_id;

     LOCK TABLE service_queue IN SHARE ROW EXCLUSIVE MODE;
     SELECT NVL(MAX(queue_number),0) + 1 INTO v_qnum
       FROM service_queue WHERE queue_type = 'OPD' AND queue_date = TRUNC(p_appt_date);
     INSERT INTO service_queue (queue_type, queue_number, queue_date, patient_id, doctor_id,
                                department_id, priority_level)
     VALUES ('OPD', v_qnum, TRUNC(p_appt_date), p_patient_id, p_doctor_id, v_dept_id,
             determine_appointment_priority(p_patient_id,'OPD'));
     COMMIT;
EXCEPTION
     WHEN OTHERS THEN
         ROLLBACK;      -- neither the appointment nor the queue token survives
         RAISE;
END book_appointment;
/

-- ---------------------------------------------------------------------
-- admit_patient - row lock on the bed (SELECT ... FOR UPDATE) so two nurses
-- cannot admit two patients into the same bed concurrently.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE admit_patient(
     p_patient_id IN NUMBER, p_room_bed_id IN NUMBER, p_doctor_id IN NUMBER,
     p_reason IN VARCHAR2, p_admission_id OUT NUMBER
) IS
     v_status room_bed.status%TYPE;
BEGIN
     SELECT status INTO v_status FROM room_bed WHERE room_bed_id = p_room_bed_id FOR UPDATE;
     IF v_status != 'AVAILABLE' THEN
         RAISE_APPLICATION_ERROR(-20002, 'Selected bed is not available (status ' || v_status || ').');
     END IF;
     INSERT INTO admission (patient_id, room_bed_id, admitting_doctor_id, admission_reason)
     VALUES (p_patient_id, p_room_bed_id, p_doctor_id, p_reason)
     RETURNING admission_id INTO p_admission_id;
     COMMIT;    -- bed status flips via trg_bed_status_update
EXCEPTION
     WHEN NO_DATA_FOUND THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20002, 'Bed ' || p_room_bed_id || ' does not exist.');
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END admit_patient;
/

-- ---------------------------------------------------------------------
-- transfer_bed - moves an admitted patient to another bed ATOMICALLY.
-- Both beds are locked in ascending room_bed_id order: if two transfers
-- run concurrently they always lock in the same order, so they can never
-- wait for each other in a cycle (deadlock prevention by lock ordering).
-- trg_bed_status_update frees the old bed and occupies the new one.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE transfer_bed(p_admission_id IN NUMBER, p_new_bed_id IN NUMBER) IS
     v_old_bed  NUMBER;
     v_status   room_bed.status%TYPE;
     CURSOR c_beds(a NUMBER, b NUMBER) IS
         SELECT room_bed_id, status FROM room_bed
          WHERE room_bed_id IN (a, b) ORDER BY room_bed_id FOR UPDATE;
BEGIN
     SELECT room_bed_id INTO v_old_bed FROM admission
      WHERE admission_id = p_admission_id AND status = 'ADMITTED' FOR UPDATE;
     FOR r IN c_beds(v_old_bed, p_new_bed_id) LOOP
         IF r.room_bed_id = p_new_bed_id THEN v_status := r.status; END IF;
     END LOOP;
     IF v_status IS NULL OR v_status != 'AVAILABLE' THEN
         RAISE_APPLICATION_ERROR(-20002, 'Target bed is not available.');
     END IF;
     UPDATE admission SET room_bed_id = p_new_bed_id WHERE admission_id = p_admission_id;
     COMMIT;
EXCEPTION
     WHEN NO_DATA_FOUND THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20003, 'Admission not found or patient already discharged.');
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END transfer_bed;
/

-- ---------------------------------------------------------------------
-- generate_bill - consultation fee + every lab test ordered on the same
-- day by the same doctor for this patient, in one transaction.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE generate_bill(
     p_patient_id IN NUMBER, p_appointment_id IN NUMBER, p_bill_id OUT NUMBER
) IS
     v_fee      NUMBER;
     v_doc      NUMBER;
     v_date     DATE;
     v_patient  NUMBER;
     v_existing NUMBER;
BEGIN
     SELECT doc.consultation_fee, a.doctor_id, a.appt_date, a.patient_id
       INTO v_fee, v_doc, v_date, v_patient
       FROM appointment a JOIN doctor doc ON doc.doctor_id = a.doctor_id
      WHERE a.appointment_id = p_appointment_id;
     IF v_patient != p_patient_id THEN
         RAISE_APPLICATION_ERROR(-20050, 'Appointment ' || p_appointment_id || ' belongs to another patient.');
     END IF;
     SELECT COUNT(*) INTO v_existing FROM bill
      WHERE appointment_id = p_appointment_id AND status != 'CANCELLED';
     IF v_existing > 0 THEN
         RAISE_APPLICATION_ERROR(-20041, 'A bill already exists for appointment ' || p_appointment_id || '.');
     END IF;

     INSERT INTO bill (patient_id, appointment_id) VALUES (p_patient_id, p_appointment_id)
     RETURNING bill_id INTO p_bill_id;
     INSERT INTO bill_item (bill_id, item_description, item_category, amount)
     VALUES (p_bill_id, 'Consultation fee', 'CONSULTATION', v_fee);
     -- INSERT ... SELECT: one statement adds every lab test of that visit
     INSERT INTO bill_item (bill_id, item_description, item_category, amount)
     SELECT p_bill_id, ltc.test_name, 'LAB_TEST', ltc.price
       FROM lab_order lo JOIN lab_test_catalog ltc ON ltc.lab_test_id = lo.lab_test_id
      WHERE lo.patient_id = p_patient_id AND lo.doctor_id = v_doc
        AND TRUNC(lo.order_date) = TRUNC(v_date) AND lo.status != 'CANCELLED';
     COMMIT;
EXCEPTION
     WHEN NO_DATA_FOUND THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20032, 'Appointment ' || p_appointment_id || ' not found.');
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END generate_bill;
/

-- ---------------------------------------------------------------------
-- record_payment - concurrency-safe payment.
-- SELECT ... FOR UPDATE locks the BILL row, so two billing clerks paying
-- the same bill at the same time are serialised: the second one waits,
-- then sees the first payment and cannot over-pay (prevents the "lost
-- update" anomaly). Bill status is then flipped by trg_bill_status_update.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE record_payment(
     p_bill_id IN NUMBER, p_amount IN NUMBER, p_mode IN VARCHAR2, p_payment_id OUT NUMBER
) IS
     v_status  bill.status%TYPE;
     v_balance NUMBER;
BEGIN
     SELECT status INTO v_status FROM bill WHERE bill_id = p_bill_id FOR UPDATE;
     IF v_status = 'CANCELLED' THEN
         RAISE_APPLICATION_ERROR(-20041, 'Bill ' || p_bill_id || ' is cancelled.');
     END IF;
     v_balance := fn_bill_balance(p_bill_id);
     IF p_amount > v_balance THEN
         RAISE_APPLICATION_ERROR(-20040, 'Payment ' || p_amount || ' exceeds outstanding balance ' || v_balance || '.');
     END IF;
     INSERT INTO payment (bill_id, amount_paid, payment_mode)
     VALUES (p_bill_id, p_amount, p_mode)
     RETURNING payment_id INTO p_payment_id;
     COMMIT;
EXCEPTION
     WHEN NO_DATA_FOUND THEN
         ROLLBACK;
         RAISE_APPLICATION_ERROR(-20041, 'Bill ' || p_bill_id || ' not found.');
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END record_payment;
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
         ROLLBACK;     -- e.g. -20011 (stock) undoes the prescription header too
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
EXCEPTION
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END register_lab_order;
/

-- ---------------------------------------------------------------------
-- update_patient - UPDATE with "only overwrite what was supplied"
-- semantics (NVL(new, old)). trg_patient_audit logs the before/after.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE update_patient(
     p_patient_id IN NUMBER,
     p_first_name IN VARCHAR2 DEFAULT NULL, p_last_name IN VARCHAR2 DEFAULT NULL,
     p_phone IN VARCHAR2 DEFAULT NULL, p_email IN VARCHAR2 DEFAULT NULL,
     p_address IN VARCHAR2 DEFAULT NULL, p_city IN VARCHAR2 DEFAULT NULL, p_blood_group IN VARCHAR2 DEFAULT NULL,
     p_ec_name IN VARCHAR2 DEFAULT NULL, p_ec_phone IN VARCHAR2 DEFAULT NULL
) IS
BEGIN
     UPDATE patient
        SET first_name  = NVL(p_first_name, first_name),
            last_name   = NVL(p_last_name, last_name),
            phone       = NVL(p_phone, phone),
            email       = NVL(p_email, email),
            address     = NVL(p_address, address),
            city        = NVL(p_city, city),
            blood_group = NVL(p_blood_group, blood_group),
            emergency_contact_name  = NVL(p_ec_name, emergency_contact_name),
            emergency_contact_phone = NVL(p_ec_phone, emergency_contact_phone)
      WHERE patient_id = p_patient_id;
     IF SQL%ROWCOUNT = 0 THEN
         RAISE_APPLICATION_ERROR(-20030, 'Patient ' || p_patient_id || ' not found.');
     END IF;
     COMMIT;
EXCEPTION
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END update_patient;
/

-- ---------------------------------------------------------------------
-- delete_patient - DELETE that respects referential integrity.
-- A patient with clinical/financial history must NOT be deleted (medical
-- records retention); only a patient registered by mistake (no visits,
-- no bills) can be removed. Without this check Oracle itself would refuse
-- with ORA-02292 (child record found) - the procedure turns that into a
-- readable message that lists what is blocking the delete.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE delete_patient(p_patient_id IN NUMBER) IS
     v_appts NUMBER; v_adm NUMBER; v_bills NUMBER; v_rx NUMBER; v_labs NUMBER; v_q NUMBER;
BEGIN
     SELECT (SELECT COUNT(*) FROM appointment  WHERE patient_id = p_patient_id),
            (SELECT COUNT(*) FROM admission    WHERE patient_id = p_patient_id),
            (SELECT COUNT(*) FROM bill         WHERE patient_id = p_patient_id),
            (SELECT COUNT(*) FROM prescription WHERE patient_id = p_patient_id),
            (SELECT COUNT(*) FROM lab_order    WHERE patient_id = p_patient_id),
            (SELECT COUNT(*) FROM service_queue WHERE patient_id = p_patient_id)
       INTO v_appts, v_adm, v_bills, v_rx, v_labs, v_q
       FROM dual;
     IF v_appts + v_adm + v_bills + v_rx + v_labs + v_q > 0 THEN
         RAISE_APPLICATION_ERROR(-20031,
             'Cannot delete patient ' || p_patient_id || ': has ' || v_appts || ' appointment(s), ' ||
             v_adm || ' admission(s), ' || v_bills || ' bill(s), ' || v_rx || ' prescription(s), ' ||
             v_labs || ' lab order(s), ' || v_q || ' queue entr(ies). Medical records must be retained.');
     END IF;
     DELETE FROM insurance_policy WHERE patient_id = p_patient_id;
     DELETE FROM vital_sign       WHERE patient_id = p_patient_id;
     DELETE FROM patient          WHERE patient_id = p_patient_id;
     IF SQL%ROWCOUNT = 0 THEN
         RAISE_APPLICATION_ERROR(-20030, 'Patient ' || p_patient_id || ' not found.');
     END IF;
     COMMIT;
EXCEPTION
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END delete_patient;
/

-- ---------------------------------------------------------------------
-- cancel_appointment - status change + removal of the patient's waiting
-- OPD token for that day, together (atomic).
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE cancel_appointment(p_appointment_id IN NUMBER) IS
     v_patient NUMBER; v_doctor NUMBER; v_date DATE;
BEGIN
     UPDATE appointment SET status = 'CANCELLED'
      WHERE appointment_id = p_appointment_id AND status = 'SCHEDULED'
     RETURNING patient_id, doctor_id, appt_date INTO v_patient, v_doctor, v_date;
     IF SQL%ROWCOUNT = 0 THEN
         RAISE_APPLICATION_ERROR(-20032, 'Appointment ' || p_appointment_id || ' not found or not SCHEDULED.');
     END IF;
     UPDATE service_queue SET status = 'CANCELLED'
      WHERE patient_id = v_patient AND doctor_id = v_doctor AND queue_date = v_date
        AND queue_type = 'OPD' AND status = 'WAITING';
     COMMIT;
EXCEPTION
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END cancel_appointment;
/

-- ---------------------------------------------------------------------
-- reschedule_appointment - SAVEPOINT demo. If the new slot is taken
-- (UNIQUE uq_doctor_timeslot / uq_patient_timeslot -> DUP_VAL_ON_INDEX)
-- we roll back ONLY to the savepoint and raise a friendly error.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE reschedule_appointment(
     p_appointment_id IN NUMBER, p_new_date IN DATE, p_new_time IN VARCHAR2
) IS
BEGIN
     IF TRUNC(p_new_date) < TRUNC(SYSDATE) THEN
         RAISE_APPLICATION_ERROR(-20004, 'New date cannot be in the past.');
     END IF;
     SAVEPOINT before_reschedule;
     UPDATE appointment SET appt_date = TRUNC(p_new_date), appt_time = p_new_time
      WHERE appointment_id = p_appointment_id AND status = 'SCHEDULED';
     IF SQL%ROWCOUNT = 0 THEN
         RAISE_APPLICATION_ERROR(-20032, 'Appointment ' || p_appointment_id || ' not found or not SCHEDULED.');
     END IF;
     COMMIT;
EXCEPTION
     WHEN DUP_VAL_ON_INDEX THEN
         ROLLBACK TO before_reschedule;
         RAISE_APPLICATION_ERROR(-20033, 'That slot is already booked for this doctor or patient.');
     WHEN OTHERS THEN
         ROLLBACK;
         RAISE;
END reschedule_appointment;
/

-- ---------------------------------------------------------------------
-- check_encounter_patient - shared by the consistency triggers in
-- 10_triggers.sql: a diagnosis / prescription / bill / vital / note that
-- points at an appointment or admission must belong to the SAME patient.
-- (patient_id is stored redundantly in those tables for fast look-ups;
-- this keeps the redundancy from ever becoming an inconsistency.)
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE check_encounter_patient(
     p_patient_id IN NUMBER, p_appointment_id IN NUMBER, p_admission_id IN NUMBER, p_table IN VARCHAR2
) IS
     v_pid NUMBER;
BEGIN
     IF p_appointment_id IS NOT NULL THEN
         SELECT patient_id INTO v_pid FROM appointment WHERE appointment_id = p_appointment_id;
         IF v_pid != p_patient_id THEN
             RAISE_APPLICATION_ERROR(-20050, p_table || ': appointment ' || p_appointment_id ||
                                     ' belongs to patient ' || v_pid || ', not ' || p_patient_id || '.');
         END IF;
     END IF;
     IF p_admission_id IS NOT NULL THEN
         SELECT patient_id INTO v_pid FROM admission WHERE admission_id = p_admission_id;
         IF v_pid != p_patient_id THEN
             RAISE_APPLICATION_ERROR(-20050, p_table || ': admission ' || p_admission_id ||
                                     ' belongs to patient ' || v_pid || ', not ' || p_patient_id || '.');
         END IF;
     END IF;
EXCEPTION
     WHEN NO_DATA_FOUND THEN NULL;   -- the FK constraint reports a missing parent
END check_encounter_patient;
/
