-- =====================================================================
-- 04b_bulk_data.sql
-- MediCore HCMS - Optional PL/SQL volume booster.
-- Generates 200 additional realistic appointments across existing
-- patients/doctors so aggregate/window-function demos have non-trivial
-- results. Run AFTER 04_sample_data.sql.
-- =====================================================================
DECLARE
    v_patient_id NUMBER;
    v_doctor_id  NUMBER;
    v_date       DATE;
    v_hour       NUMBER;
BEGIN
    FOR i IN 1..200 LOOP
        SELECT patient_id INTO v_patient_id FROM (
            SELECT patient_id FROM patient ORDER BY DBMS_RANDOM.VALUE
        ) WHERE ROWNUM = 1;
        SELECT doctor_id INTO v_doctor_id FROM (
            SELECT doctor_id FROM doctor ORDER BY DBMS_RANDOM.VALUE
        ) WHERE ROWNUM = 1;
        v_date := TRUNC(SYSDATE) - TRUNC(DBMS_RANDOM.VALUE(1,60));
        v_hour := TRUNC(DBMS_RANDOM.VALUE(9,17));
        BEGIN
            INSERT INTO appointment (patient_id, doctor_id, appt_date, appt_time, appt_type, status, reason)
            VALUES (
                v_patient_id, v_doctor_id, v_date,
                LPAD(v_hour,2,'0') || ':' || CASE WHEN DBMS_RANDOM.VALUE < 0.5 THEN '00' ELSE '30' END,
                CASE WHEN DBMS_RANDOM.VALUE < 0.3 THEN 'FOLLOW_UP' ELSE 'NEW' END,
                CASE WHEN DBMS_RANDOM.VALUE < 0.12 THEN 'NO_SHOW'
                     WHEN DBMS_RANDOM.VALUE < 0.9 THEN 'COMPLETED'
                     ELSE 'CANCELLED' END,
                'Auto-generated demo visit'
            );
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN NULL; -- skip slot clash, try next iteration
    END LOOP;

    -- Generate upcoming SCHEDULED appointments across the next 14 days
    -- so that ml/predict_and_store.py and the AI/ML Insights dashboard
    -- have upcoming appointments to score and display.
    FOR i IN 1..40 LOOP
        SELECT patient_id INTO v_patient_id FROM (
            SELECT patient_id FROM patient ORDER BY DBMS_RANDOM.VALUE
        ) WHERE ROWNUM = 1;
        SELECT doctor_id INTO v_doctor_id FROM (
            SELECT doctor_id FROM doctor ORDER BY DBMS_RANDOM.VALUE
        ) WHERE ROWNUM = 1;
        v_date := TRUNC(SYSDATE) + TRUNC(DBMS_RANDOM.VALUE(0,14));
        v_hour := TRUNC(DBMS_RANDOM.VALUE(9,17));
        BEGIN
            INSERT INTO appointment (patient_id, doctor_id, appt_date, appt_time, appt_type, status, reason)
            VALUES (
                v_patient_id, v_doctor_id, v_date,
                LPAD(v_hour,2,'0') || ':' || CASE WHEN DBMS_RANDOM.VALUE < 0.5 THEN '00' ELSE '30' END,
                CASE WHEN DBMS_RANDOM.VALUE < 0.4 THEN 'NEW' ELSE 'FOLLOW_UP' END,
                'SCHEDULED',
                'Scheduled appointment'
            );
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN NULL;
        END;
    END LOOP;
    COMMIT;
END;
/
