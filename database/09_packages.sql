-- =====================================================================
-- 09_packages.sql
-- MediCore HCMS - pkg_clinical_ops package. Run AFTER 08_procedures.sql.
-- NOTE: hcms_admin below is the schema owner (Phase 11) that owns the
-- standalone procedures in 08_procedures.sql. Adjust the schema prefix
-- if you run everything under a different user.
-- =====================================================================
CREATE OR REPLACE PACKAGE pkg_clinical_ops AS
    PROCEDURE book_appointment(p_patient_id NUMBER, p_doctor_id NUMBER, p_appt_date DATE,
                                p_appt_time VARCHAR2, p_reason VARCHAR2, p_appointment_id OUT NUMBER);
    PROCEDURE discharge_patient(p_admission_id NUMBER);
    FUNCTION get_active_prescription_count(p_patient_id NUMBER) RETURN NUMBER;
END pkg_clinical_ops;
/
CREATE OR REPLACE PACKAGE BODY pkg_clinical_ops AS
    PROCEDURE book_appointment(p_patient_id NUMBER, p_doctor_id NUMBER, p_appt_date DATE,
                                p_appt_time VARCHAR2, p_reason VARCHAR2, p_appointment_id OUT NUMBER) IS
    BEGIN
        -- delegates to the standalone procedure to avoid duplicating logic
        hcms_admin.book_appointment(p_patient_id, p_doctor_id, p_appt_date, p_appt_time, p_reason, p_appointment_id);
    END;
    PROCEDURE discharge_patient(p_admission_id NUMBER) IS
    BEGIN
        UPDATE admission SET status = 'DISCHARGED', discharge_date = SYSDATE
        WHERE admission_id = p_admission_id AND status = 'ADMITTED';
        IF SQL%ROWCOUNT = 0 THEN
            RAISE_APPLICATION_ERROR(-20003, 'Admission not found or already discharged.');
        END IF;
        COMMIT;    -- bed freed via trg_bed_status_update
    EXCEPTION
        WHEN OTHERS THEN ROLLBACK; RAISE;
    END discharge_patient;
    FUNCTION get_active_prescription_count(p_patient_id NUMBER) RETURN NUMBER IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM prescription
        WHERE patient_id = p_patient_id AND status = 'ACTIVE';
        RETURN v_count;
    END get_active_prescription_count;
END pkg_clinical_ops;
/
-- Why a package here: grouping book_appointment (re-exposed for callers who
-- prefer the package namespace), discharge_patient, and a helper function
-- lets related clinical operations share one compiled unit, one set of
-- grants (GRANT EXECUTE ON pkg_clinical_ops), and hides body implementation
-- changes from callers (package spec is stable even if body logic evolves).
