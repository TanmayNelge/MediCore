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
