-- =====================================================================
-- 07_functions.sql
-- MediCore HCMS - Standalone PL/SQL functions. Run AFTER schema/data.
-- =====================================================================
-- Calculate age from DOB (kept as a function, never a stored column - Phase 3)
CREATE OR REPLACE FUNCTION calculate_age(p_dob IN DATE) RETURN NUMBER IS
BEGIN
    RETURN TRUNC(MONTHS_BETWEEN(SYSDATE, p_dob) / 12);
END calculate_age;
/
-- BMI = weight(kg) / height(m)^2
CREATE OR REPLACE FUNCTION calculate_bmi(p_weight_kg IN NUMBER, p_height_cm IN NUMBER) RETURN NUMBER IS
BEGIN
    IF p_height_cm IS NULL OR p_height_cm = 0 THEN
        RETURN NULL;
    END IF;
    RETURN ROUND(p_weight_kg / POWER(p_height_cm/100, 2), 2);
END calculate_bmi;
/
-- Total amount for a bill (derived, never stored - Phase 3)
CREATE OR REPLACE FUNCTION calculate_bill_total(p_bill_id IN NUMBER) RETURN NUMBER IS
    v_total NUMBER := 0;
BEGIN
    SELECT NVL(SUM(amount),0) INTO v_total FROM bill_item WHERE bill_id = p_bill_id;
    RETURN v_total;
END calculate_bill_total;
/
-- Appointment priority for the queue: EMERGENCY type -> 1, elderly/child NEW visit -> 2, else 3
CREATE OR REPLACE FUNCTION determine_appointment_priority(
    p_patient_id IN NUMBER, p_queue_type IN VARCHAR2
) RETURN NUMBER IS
    v_age NUMBER;
BEGIN
    IF p_queue_type = 'EMERGENCY' THEN
         RETURN 1;
    END IF;
    SELECT calculate_age(dob) INTO v_age FROM patient WHERE patient_id = p_patient_id;
    IF v_age < 12 OR v_age > 65 THEN
         RETURN 2;
    ELSE
         RETURN 3;
    END IF;
EXCEPTION
    WHEN NO_DATA_FOUND THEN RETURN 3;
END determine_appointment_priority;
/

-- =====================================================================
-- v2 additions
-- =====================================================================

-- Maps the Oracle login (SESSION_USER, e.g. DOCTOR1) to APP_USER.user_id so
-- every AUDIT_LOG row records WHO made the change. Triggers run with the
-- owner's (definer) rights, but SESSION_USER is still the real login.
CREATE OR REPLACE FUNCTION current_app_user_id RETURN NUMBER IS
    v_id app_user.user_id%TYPE;
BEGIN
    SELECT user_id INTO v_id
      FROM app_user
     WHERE UPPER(username) = SYS_CONTEXT('USERENV', 'SESSION_USER');
    RETURN v_id;
EXCEPTION
    WHEN NO_DATA_FOUND THEN RETURN NULL;   -- e.g. HCMS_ADMIN / SYSTEM sessions
END current_app_user_id;
/

-- Historic no-show rate of a patient (resolved appointments only).
-- Used by reports and handy in the viva: SELECT fn_patient_no_show_rate(12) FROM dual;
CREATE OR REPLACE FUNCTION fn_patient_no_show_rate(p_patient_id IN NUMBER) RETURN NUMBER IS
    v_total   NUMBER;
    v_noshow  NUMBER;
BEGIN
    SELECT COUNT(*), NVL(SUM(CASE WHEN status = 'NO_SHOW' THEN 1 ELSE 0 END), 0)
      INTO v_total, v_noshow
      FROM appointment
     WHERE patient_id = p_patient_id
       AND status IN ('COMPLETED', 'NO_SHOW');
    IF v_total = 0 THEN
        RETURN NULL;
    END IF;
    RETURN ROUND(v_noshow / v_total, 4);
END fn_patient_no_show_rate;
/

-- Outstanding balance of a bill = SUM(bill_item.amount) - SUM(payment.amount_paid)
-- (derived on read, never stored - storing it would create an update anomaly)
CREATE OR REPLACE FUNCTION fn_bill_balance(p_bill_id IN NUMBER) RETURN NUMBER IS
    v_paid NUMBER;
BEGIN
    SELECT NVL(SUM(amount_paid), 0) INTO v_paid FROM payment WHERE bill_id = p_bill_id;
    RETURN calculate_bill_total(p_bill_id) - v_paid;
END fn_bill_balance;
/
