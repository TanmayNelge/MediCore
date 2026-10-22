-- =====================================================================
-- 12_security_roles.sql
-- MediCore HCMS - database users, roles, password profile and the
-- least-privilege GRANT matrix.  Run as SYSTEM (or any DBA) AFTER every
-- HCMS_ADMIN object exists (install.py does this automatically).
--
-- v2 - WHAT WAS WRONG BEFORE (all verified against the routers that use
-- each role's connection):
--   * ADMIN_ROLE had no SELECT on DEPARTMENT, DOCTOR, NURSE, LAB_TEST_CATALOG,
--     INSURANCE_POLICY, ML_PREDICTION ... and no EXECUTE on book_appointment,
--     admit_patient, generate_bill, the queue procedures or calculate_age.
--     admin1 got ORA-00942 on /doctors, ORA-06550 on booking, and the ML
--     pipeline (which logs in as admin1) could not read DOCTOR or write
--     ML_PREDICTION.
--   * READONLY_ROLE (used by Reports, Dashboard and the AI/ML page) had no
--     SELECT on ML_PREDICTION -> the ML page always failed.
--   * Every role that uses a lookup dropdown (doctor list) lacked SELECT on
--     DOCTOR; LAB_ROLE could not read LAB_TEST_CATALOG; PHARMACY_ROLE could
--     not read PRESCRIPTION; BILLING_ROLE could not EXECUTE generate_bill;
--     RECEPTIONIST/NURSE could not EXECUTE admit_patient or the queue
--     procedures their screens call.
--   * The application accepted ANY username==password without asking
--     Oracle (fixed in backend/app/routers/auth.py) - now Oracle checks
--     every login and this file adds a password/lock-out PROFILE.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Password profile (authentication hardening)
-- ---------------------------------------------------------------------
CREATE PROFILE hcms_staff_profile LIMIT
    FAILED_LOGIN_ATTEMPTS 10          -- lock after 10 wrong passwords
    PASSWORD_LOCK_TIME    1/96        -- ... for 15 minutes
    SESSIONS_PER_USER     UNLIMITED;
-- Deliberately NOT set for this demo (install.py re-sets password = username
-- on every install, and the accounts must not expire during a viva):
--   PASSWORD_LIFE_TIME 90, PASSWORD_REUSE_MAX 5, PASSWORD_REUSE_TIME 180,
--   PASSWORD_VERIFY_FUNCTION ORA12C_VERIFY_FUNCTION  -- use these in production.

-- ---------------------------------------------------------------------
-- 2. Users (demo passwords == username; install.py resets them)
-- ---------------------------------------------------------------------
CREATE USER receptionist1 IDENTIFIED BY "receptionist1" PROFILE hcms_staff_profile;
CREATE USER doctor1       IDENTIFIED BY "doctor1"       PROFILE hcms_staff_profile;
CREATE USER labtech1      IDENTIFIED BY "labtech1"      PROFILE hcms_staff_profile;
CREATE USER pharmacist1   IDENTIFIED BY "pharmacist1"   PROFILE hcms_staff_profile;
CREATE USER billingclerk1 IDENTIFIED BY "billingclerk1" PROFILE hcms_staff_profile;
CREATE USER admin1        IDENTIFIED BY "admin1"        PROFILE hcms_staff_profile;
CREATE USER nurse1        IDENTIFIED BY "nurse1"        PROFILE hcms_staff_profile;
CREATE USER readonly1     IDENTIFIED BY "readonly1"     PROFILE hcms_staff_profile;

-- users that already existed from an earlier install get the profile too
ALTER USER receptionist1 PROFILE hcms_staff_profile;
ALTER USER doctor1       PROFILE hcms_staff_profile;
ALTER USER labtech1      PROFILE hcms_staff_profile;
ALTER USER pharmacist1   PROFILE hcms_staff_profile;
ALTER USER billingclerk1 PROFILE hcms_staff_profile;
ALTER USER admin1        PROFILE hcms_staff_profile;
ALTER USER nurse1        PROFILE hcms_staff_profile;
ALTER USER readonly1     PROFILE hcms_staff_profile;

GRANT CREATE SESSION TO receptionist1, doctor1, labtech1, pharmacist1,
                          billingclerk1, admin1, nurse1, readonly1;

-- ---------------------------------------------------------------------
-- 3. Roles
-- ---------------------------------------------------------------------
CREATE ROLE admin_role;
CREATE ROLE doctor_role;
CREATE ROLE nurse_role;
CREATE ROLE receptionist_role;
CREATE ROLE lab_role;
CREATE ROLE pharmacy_role;
CREATE ROLE billing_role;
CREATE ROLE readonly_role;

-- ---------------------------------------------------------------------
-- 4. Grants shared by every staff role: reference data used by drop-downs
--    (no personal or clinical data in these tables)
-- ---------------------------------------------------------------------
BEGIN
    FOR r IN (SELECT column_value AS role_name FROM TABLE(sys.odcivarchar2list(
                'DOCTOR_ROLE','NURSE_ROLE','RECEPTIONIST_ROLE','LAB_ROLE','PHARMACY_ROLE','BILLING_ROLE'))) LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.department TO ' || r.role_name;
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.doctor TO '     || r.role_name;
    END LOOP;
END;
/

-- ---------------------------------------------------------------------
-- 5. DOCTOR_ROLE - clinical read/write, NO billing
-- ---------------------------------------------------------------------
GRANT SELECT, UPDATE ON hcms_admin.patient TO doctor_role;
GRANT SELECT ON hcms_admin.appointment TO doctor_role;
-- column-level privilege: only the STATUS column may be updated
GRANT UPDATE (status) ON hcms_admin.appointment TO doctor_role;
GRANT SELECT ON hcms_admin.vw_doctor_appointment_schedule TO doctor_role;
GRANT SELECT ON hcms_admin.admission TO doctor_role;
GRANT SELECT ON hcms_admin.room_bed TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.diagnosis TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.diagnosis_symptom TO doctor_role;
GRANT SELECT ON hcms_admin.symptom TO doctor_role;
GRANT SELECT ON hcms_admin.disease TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.clinical_note TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.vital_sign TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.prescription TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.prescription_item TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.lab_order TO doctor_role;
GRANT SELECT ON hcms_admin.lab_test_catalog TO doctor_role;
GRANT SELECT ON hcms_admin.medicine TO doctor_role;
GRANT SELECT ON hcms_admin.service_queue TO doctor_role;
GRANT SELECT ON hcms_admin.vw_patient_medical_summary TO doctor_role;
GRANT SELECT ON hcms_admin.vw_pending_lab_reports TO doctor_role;
GRANT SELECT ON hcms_admin.vw_medicine_inventory_status TO doctor_role;
GRANT SELECT ON hcms_admin.vw_current_admitted_patients TO doctor_role;
GRANT SELECT ON hcms_admin.vw_emergency_queue TO doctor_role;
GRANT SELECT ON hcms_admin.seq_diagnosis_id TO doctor_role;
GRANT SELECT ON hcms_admin.seq_note_id TO doctor_role;
GRANT SELECT ON hcms_admin.seq_vital_id TO doctor_role;
GRANT EXECUTE ON hcms_admin.pkg_clinical_ops TO doctor_role;
GRANT EXECUTE ON hcms_admin.book_appointment TO doctor_role;
GRANT EXECUTE ON hcms_admin.cancel_appointment TO doctor_role;
GRANT EXECUTE ON hcms_admin.admit_patient TO doctor_role;
GRANT EXECUTE ON hcms_admin.transfer_bed TO doctor_role;
GRANT EXECUTE ON hcms_admin.add_prescription TO doctor_role;
GRANT EXECUTE ON hcms_admin.register_lab_order TO doctor_role;
GRANT EXECUTE ON hcms_admin.get_next_patient TO doctor_role;
GRANT EXECUTE ON hcms_admin.mark_queue_completed TO doctor_role;
GRANT EXECUTE ON hcms_admin.calculate_age TO doctor_role;
GRANT EXECUTE ON hcms_admin.calculate_bmi TO doctor_role;

-- ---------------------------------------------------------------------
-- 6. NURSE_ROLE - vitals & notes, sees diagnoses ONLY through the
--    summary view (view-based restricted access), NO billing
-- ---------------------------------------------------------------------
GRANT SELECT ON hcms_admin.patient TO nurse_role;
GRANT SELECT ON hcms_admin.appointment TO nurse_role;
GRANT UPDATE (status) ON hcms_admin.appointment TO nurse_role;
GRANT SELECT ON hcms_admin.vw_doctor_appointment_schedule TO nurse_role;
GRANT SELECT ON hcms_admin.admission TO nurse_role;
GRANT SELECT ON hcms_admin.room_bed TO nurse_role;
GRANT SELECT ON hcms_admin.prescription TO nurse_role;
GRANT SELECT ON hcms_admin.prescription_item TO nurse_role;
GRANT SELECT ON hcms_admin.lab_order TO nurse_role;
GRANT SELECT ON hcms_admin.lab_test_catalog TO nurse_role;
GRANT SELECT ON hcms_admin.medicine TO nurse_role;
GRANT SELECT ON hcms_admin.service_queue TO nurse_role;
GRANT SELECT, INSERT ON hcms_admin.clinical_note TO nurse_role;
GRANT SELECT, INSERT ON hcms_admin.vital_sign TO nurse_role;
GRANT SELECT ON hcms_admin.vw_patient_medical_summary TO nurse_role;
GRANT SELECT ON hcms_admin.disease TO nurse_role;
GRANT SELECT ON hcms_admin.vw_pending_lab_reports TO nurse_role;
GRANT SELECT ON hcms_admin.vw_current_admitted_patients TO nurse_role;
GRANT SELECT ON hcms_admin.vw_emergency_queue TO nurse_role;
GRANT SELECT ON hcms_admin.seq_note_id TO nurse_role;
GRANT SELECT ON hcms_admin.seq_vital_id TO nurse_role;
GRANT EXECUTE ON hcms_admin.admit_patient TO nurse_role;
GRANT EXECUTE ON hcms_admin.transfer_bed TO nurse_role;
GRANT EXECUTE ON hcms_admin.add_to_queue TO nurse_role;
GRANT EXECUTE ON hcms_admin.get_next_patient TO nurse_role;
GRANT EXECUTE ON hcms_admin.prioritize_emergency TO nurse_role;
GRANT EXECUTE ON hcms_admin.mark_queue_completed TO nurse_role;
GRANT EXECUTE ON hcms_admin.cancel_queue_entry TO nurse_role;
GRANT EXECUTE ON hcms_admin.calculate_bmi TO nurse_role;

-- ---------------------------------------------------------------------
-- 7. RECEPTIONIST_ROLE - registration, booking, admission, queue;
--    NO clinical tables at all
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON hcms_admin.patient TO receptionist_role;
GRANT SELECT ON hcms_admin.seq_patient_id TO receptionist_role;
GRANT SELECT ON hcms_admin.appointment TO receptionist_role;
GRANT UPDATE (status) ON hcms_admin.appointment TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_doctor_appointment_schedule TO receptionist_role;
GRANT SELECT ON hcms_admin.room_bed TO receptionist_role;
GRANT SELECT ON hcms_admin.admission TO receptionist_role;
GRANT SELECT ON hcms_admin.service_queue TO receptionist_role;
GRANT SELECT ON hcms_admin.insurance_policy TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_emergency_queue TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_current_admitted_patients TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_patient_billing_summary TO receptionist_role;
GRANT EXECUTE ON hcms_admin.book_appointment TO receptionist_role;
GRANT EXECUTE ON hcms_admin.cancel_appointment TO receptionist_role;
GRANT EXECUTE ON hcms_admin.reschedule_appointment TO receptionist_role;
GRANT EXECUTE ON hcms_admin.update_patient TO receptionist_role;
GRANT EXECUTE ON hcms_admin.admit_patient TO receptionist_role;
GRANT EXECUTE ON hcms_admin.add_to_queue TO receptionist_role;
GRANT EXECUTE ON hcms_admin.get_next_patient TO receptionist_role;
GRANT EXECUTE ON hcms_admin.prioritize_emergency TO receptionist_role;
GRANT EXECUTE ON hcms_admin.cancel_queue_entry TO receptionist_role;
REVOKE ALL ON hcms_admin.diagnosis FROM receptionist_role;
REVOKE ALL ON hcms_admin.clinical_note FROM receptionist_role;
REVOKE ALL ON hcms_admin.prescription FROM receptionist_role;

-- ---------------------------------------------------------------------
-- 8. LAB_ROLE - lab orders and results; patient name/contact via view only
-- ---------------------------------------------------------------------
GRANT SELECT, UPDATE ON hcms_admin.lab_order TO lab_role;
GRANT SELECT ON hcms_admin.lab_test_catalog TO lab_role;
GRANT SELECT ON hcms_admin.vw_pending_lab_reports TO lab_role;
GRANT SELECT ON hcms_admin.vw_patient_directory TO lab_role;
GRANT SELECT ON hcms_admin.vw_lab_turnaround TO lab_role;
GRANT EXECUTE ON hcms_admin.add_to_queue TO lab_role;
REVOKE ALL ON hcms_admin.diagnosis FROM lab_role;
REVOKE ALL ON hcms_admin.bill FROM lab_role;

-- ---------------------------------------------------------------------
-- 9. PHARMACY_ROLE - dispensing and stock; patient name via view only
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON hcms_admin.medicine TO pharmacy_role;
GRANT SELECT ON hcms_admin.seq_medicine_id TO pharmacy_role;
GRANT SELECT ON hcms_admin.prescription TO pharmacy_role;
-- column-level privilege: mark a prescription FULFILLED
GRANT UPDATE (status) ON hcms_admin.prescription TO pharmacy_role;
GRANT SELECT, UPDATE ON hcms_admin.prescription_item TO pharmacy_role;
GRANT SELECT ON hcms_admin.vw_medicine_inventory_status TO pharmacy_role;
GRANT SELECT ON hcms_admin.vw_patient_directory TO pharmacy_role;
REVOKE ALL ON hcms_admin.diagnosis FROM pharmacy_role;

-- ---------------------------------------------------------------------
-- 10. BILLING_ROLE - money only; NO diagnosis / notes / prescriptions
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON hcms_admin.bill TO billing_role;
GRANT SELECT, INSERT ON hcms_admin.bill_item TO billing_role;
GRANT SELECT, INSERT ON hcms_admin.payment TO billing_role;
GRANT SELECT ON hcms_admin.seq_bill_id TO billing_role;
GRANT SELECT ON hcms_admin.seq_bill_item_id TO billing_role;
GRANT SELECT ON hcms_admin.seq_payment_id TO billing_role;
GRANT SELECT ON hcms_admin.appointment TO billing_role;
GRANT SELECT ON hcms_admin.insurance_policy TO billing_role;
GRANT SELECT ON hcms_admin.vw_patient_billing_summary TO billing_role;
GRANT SELECT ON hcms_admin.vw_outstanding_bills TO billing_role;
GRANT SELECT ON hcms_admin.vw_department_revenue TO billing_role;
GRANT SELECT ON hcms_admin.vw_patient_directory TO billing_role;
GRANT EXECUTE ON hcms_admin.generate_bill TO billing_role;
GRANT EXECUTE ON hcms_admin.record_payment TO billing_role;
GRANT EXECUTE ON hcms_admin.fn_bill_balance TO billing_role;
REVOKE ALL ON hcms_admin.diagnosis FROM billing_role;
REVOKE ALL ON hcms_admin.clinical_note FROM billing_role;
REVOKE ALL ON hcms_admin.prescription FROM billing_role;

-- ---------------------------------------------------------------------
-- 11. ADMIN_ROLE - full DML on every table, EXCEPT the audit trail which
--     is append-only for everybody (SELECT only - even an administrator
--     must not be able to erase the evidence of what he changed).
--     Generated from the data dictionary so no table can be forgotten.
-- ---------------------------------------------------------------------
BEGIN
    FOR t IN (SELECT table_name FROM dba_tables WHERE owner = 'HCMS_ADMIN' AND table_name != 'AUDIT_LOG') LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.' || t.table_name || ' TO admin_role';
    END LOOP;
    EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.audit_log TO admin_role';
    FOR v IN (SELECT view_name FROM dba_views WHERE owner = 'HCMS_ADMIN') LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.' || v.view_name || ' TO admin_role';
    END LOOP;
    FOR s IN (SELECT sequence_name FROM dba_sequences WHERE sequence_owner = 'HCMS_ADMIN') LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.' || s.sequence_name || ' TO admin_role';
    END LOOP;
    FOR p IN (SELECT object_name FROM dba_objects WHERE owner = 'HCMS_ADMIN'
                AND object_type IN ('PROCEDURE','FUNCTION','PACKAGE')) LOOP
        EXECUTE IMMEDIATE 'GRANT EXECUTE ON hcms_admin.' || p.object_name || ' TO admin_role';
    END LOOP;
END;
/

-- ---------------------------------------------------------------------
-- 12. READONLY_ROLE - SELECT on every table and view except the internal
--     APP_USER / AUDIT_LOG tables, plus EXECUTE on the pure functions.
--     Backs Reports, Dashboard, AI/ML insights and the DBMS-Lab SQL
--     sandbox: whatever SQL is typed there, Oracle itself refuses to
--     change data (ORA-01031 insufficient privileges).
-- ---------------------------------------------------------------------
BEGIN
    FOR t IN (SELECT table_name FROM dba_tables WHERE owner = 'HCMS_ADMIN'
                AND table_name NOT IN ('APP_USER','AUDIT_LOG')) LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.' || t.table_name || ' TO readonly_role';
    END LOOP;
    FOR v IN (SELECT view_name FROM dba_views WHERE owner = 'HCMS_ADMIN') LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON hcms_admin.' || v.view_name || ' TO readonly_role';
    END LOOP;
    FOR f IN (SELECT column_value AS fn FROM TABLE(sys.odcivarchar2list(
                'CALCULATE_AGE','CALCULATE_BMI','CALCULATE_BILL_TOTAL','FN_BILL_BALANCE',
                'FN_PATIENT_NO_SHOW_RATE','DETERMINE_APPOINTMENT_PRIORITY'))) LOOP
        EXECUTE IMMEDIATE 'GRANT EXECUTE ON hcms_admin.' || f.fn || ' TO readonly_role';
    END LOOP;
END;
/

-- ---------------------------------------------------------------------
-- 13. Assign roles to users
-- ---------------------------------------------------------------------
GRANT doctor_role       TO doctor1;
GRANT receptionist_role TO receptionist1;
GRANT lab_role          TO labtech1;
GRANT pharmacy_role     TO pharmacist1;
GRANT billing_role      TO billingclerk1;
GRANT admin_role        TO admin1;
GRANT nurse_role        TO nurse1;
GRANT readonly_role     TO readonly1;

-- ---------------------------------------------------------------------
-- Verify (run as SYSTEM):
--   SELECT grantee, table_name, privilege FROM dba_tab_privs
--    WHERE owner = 'HCMS_ADMIN' AND grantee LIKE '%ROLE' ORDER BY 1, 2;
--   SELECT * FROM dba_col_privs WHERE owner = 'HCMS_ADMIN';   -- column-level UPDATE(status)
-- Try it (connected as receptionist1):
--   SELECT * FROM hcms_admin.diagnosis;          -> ORA-00942 (no privilege)
--   UPDATE hcms_admin.appointment SET reason='x' WHERE appointment_id=1;
--                                               -> ORA-01031 (only UPDATE(status) granted)
--
-- Security features discussion (report/viva):
--   - Authentication: every login is checked by Oracle; profile above locks
--     brute-force attempts.            - Authorisation: roles + least privilege.
--   - Column-level privileges: UPDATE(status) only.
--   - View-based restriction: vw_patient_directory hides address/DOB/clinical data.
--   - Audit: append-only AUDIT_LOG written by triggers with the real user id.
--   - SQL injection: backend uses bind variables only; the SQL sandbox is
--     backed by a SELECT-only account (defence in depth).
--   - Integrity: PK/FK/UNIQUE/CHECK constraints + consistency triggers.
--   - Encryption (TDE / DBMS_CRYPTO) and backups (RMAN / Data Pump) are
--     production concerns, discussed but not part of this build.
-- ---------------------------------------------------------------------
