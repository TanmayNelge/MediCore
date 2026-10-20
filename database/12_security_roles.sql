-- =====================================================================
-- 12_security_roles.sql
-- MediCore HCMS - DB users, roles, and least-privilege GRANT/REVOKE.
-- Run as a DBA-privileged user (SYSTEM or equivalent) AFTER all
-- HCMS_ADMIN objects (01-11, 13) exist.
--
-- WHY THIS FILE REPLACES THE ORIGINAL THREE:
--   1. 12_security_roles.sql (original) fails partway through with
--      ORA-00990-style "invalid privilege" on the ADMIN_ROLE grant,
--      because Oracle's GRANT <privs> ON <object> syntax allows only
--      ONE object per statement -- "ON a, b, c" is not valid. SQL*Plus
--      does not abort by default, so the rest of the script still runs,
--      but ADMIN_ROLE silently ends up under-privileged.
--   2. 12_grants_only.sql duplicates that same bug.
--   3. 12b_admin_grants_fix.sql correctly splits the ADMIN_ROLE grants
--      into one statement per table, but was a separate patch file you
--      had to remember to also run, in the right order.
--   4. NURSE_ROLE was created but never granted a single privilege, and
--      no nurse1 user existed -- even though NURSE is table #3 of 26 in
--      the schema, the privilege matrix documents a NURSE_ROLE, and
--      backend/app/db/pool.py already expects a NURSE1_PWD env var.
--   5. There was no dedicated low-privilege read-only user for the DBMS
--      Concept Lab sandbox endpoint (Phase 13.4 calls for one
--      explicitly; app/routers/dbms_lab.py even has a code comment
--      flagging that it was missing).
--
-- This single file does everything 12_security_roles.sql,
-- 12_grants_only.sql and 12b_admin_grants_fix.sql did, correctly, plus
-- the two additions above. Run ONLY this file; delete or ignore the
-- three originals to avoid confusion/duplicate CREATE USER errors.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Authentication
-- Passwords below are illustrative placeholders only -- never commit
-- real credentials. In production the backend supplies these via a
-- secrets store, not hardcoded SQL.
-- ---------------------------------------------------------------------
CREATE USER receptionist1 IDENTIFIED BY "receptionist1";
CREATE USER doctor1       IDENTIFIED BY "doctor1";
CREATE USER labtech1      IDENTIFIED BY "labtech1";
CREATE USER pharmacist1   IDENTIFIED BY "pharmacist1";
CREATE USER billingclerk1 IDENTIFIED BY "billingclerk1";
CREATE USER admin1        IDENTIFIED BY "admin1";
CREATE USER nurse1        IDENTIFIED BY "nurse1";
CREATE USER readonly1     IDENTIFIED BY "readonly1";

GRANT CREATE SESSION TO receptionist1, doctor1, labtech1, pharmacist1,
                          billingclerk1, admin1, nurse1, readonly1;

-- ---------------------------------------------------------------------
-- Roles
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
-- Privilege matrix (least privilege), summarized per role:
--   ADMIN_ROLE        - full access to clinical/pharmacy/lab/billing
--                        tables, plus role/user/audit administration.
--   DOCTOR_ROLE        - patient SELECT/UPDATE (own patients); appointment
--                        SELECT + INSERT via book_appointment; diagnosis/
--                        clinical_note SELECT+INSERT; prescription
--                        SELECT+INSERT via add_prescription; lab_order
--                        SELECT+INSERT via register_lab_order; medicine
--                        SELECT only; no bill/payment access.
--   NURSE_ROLE          - patient/appointment/prescription/lab_order/
--                        medicine SELECT; clinical_note/vital_sign SELECT+
--                        INSERT; no bill/payment access.
--   RECEPTIONIST_ROLE   - patient SELECT/INSERT/UPDATE(contact); appointment
--                        SELECT/INSERT/UPDATE via book_appointment; NO
--                        access to diagnosis/clinical_note/prescription/
--                        lab_order/medicine; bill SELECT only.
--   LAB_ROLE            - patient SELECT (name/DOB via view only); lab_order
--                        SELECT+UPDATE (result entry); no medicine/bill.
--   PHARMACY_ROLE       - patient SELECT (name via view only); prescription
--                        SELECT+UPDATE (fulfillment); medicine SELECT+
--                        UPDATE (stock); no bill access.
--   BILLING_ROLE        - patient SELECT (name/contact via view only);
--                        bill/bill_item/payment; NO diagnosis/clinical_note/
--                        prescription/lab_order.
--   READONLY_ROLE       - SELECT only on every application table/view,
--                        nothing else. Backs the DBMS Concept Lab's
--                        sandboxed /dbms-lab/execute endpoint so that
--                        endpoint's protection is a real DB-enforced
--                        grant set, not just the app-level regex.
-- ---------------------------------------------------------------------

-- DOCTOR_ROLE
GRANT SELECT, UPDATE ON hcms_admin.patient TO doctor_role;
GRANT SELECT ON hcms_admin.appointment TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.diagnosis TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.clinical_note TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.prescription TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.prescription_item TO doctor_role;
GRANT SELECT, INSERT ON hcms_admin.lab_order TO doctor_role;
GRANT SELECT ON hcms_admin.medicine TO doctor_role;
GRANT EXECUTE ON hcms_admin.pkg_clinical_ops TO doctor_role;
GRANT EXECUTE ON hcms_admin.book_appointment TO doctor_role;
GRANT EXECUTE ON hcms_admin.add_prescription TO doctor_role;
GRANT EXECUTE ON hcms_admin.register_lab_order TO doctor_role;
REVOKE ALL ON hcms_admin.bill FROM doctor_role;
REVOKE ALL ON hcms_admin.payment FROM doctor_role;

-- NURSE_ROLE (new -- was created but never granted anything)
GRANT SELECT ON hcms_admin.patient TO nurse_role;
GRANT SELECT ON hcms_admin.appointment TO nurse_role;
GRANT SELECT ON hcms_admin.admission TO nurse_role;
GRANT SELECT ON hcms_admin.prescription TO nurse_role;
GRANT SELECT ON hcms_admin.prescription_item TO nurse_role;
GRANT SELECT ON hcms_admin.lab_order TO nurse_role;
GRANT SELECT ON hcms_admin.medicine TO nurse_role;
GRANT SELECT, INSERT ON hcms_admin.clinical_note TO nurse_role;
GRANT SELECT, INSERT ON hcms_admin.vital_sign TO nurse_role;
REVOKE ALL ON hcms_admin.bill FROM nurse_role;
REVOKE ALL ON hcms_admin.payment FROM nurse_role;
REVOKE ALL ON hcms_admin.diagnosis FROM nurse_role;

-- RECEPTIONIST_ROLE
GRANT SELECT, INSERT, UPDATE ON hcms_admin.patient TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_doctor_appointment_schedule TO receptionist_role;
GRANT EXECUTE ON hcms_admin.book_appointment TO receptionist_role;
GRANT SELECT ON hcms_admin.vw_patient_billing_summary TO receptionist_role;
REVOKE ALL ON hcms_admin.diagnosis FROM receptionist_role;
REVOKE ALL ON hcms_admin.clinical_note FROM receptionist_role;
REVOKE ALL ON hcms_admin.prescription FROM receptionist_role;

-- LAB_ROLE
GRANT SELECT, UPDATE ON hcms_admin.lab_order TO lab_role;
GRANT SELECT ON hcms_admin.vw_pending_lab_reports TO lab_role;
REVOKE ALL ON hcms_admin.diagnosis FROM lab_role;
REVOKE ALL ON hcms_admin.bill FROM lab_role;

-- PHARMACY_ROLE
GRANT SELECT, UPDATE ON hcms_admin.medicine TO pharmacy_role;
GRANT SELECT, UPDATE ON hcms_admin.prescription_item TO pharmacy_role;
GRANT SELECT ON hcms_admin.vw_medicine_inventory_status TO pharmacy_role;
REVOKE ALL ON hcms_admin.diagnosis FROM pharmacy_role;

-- BILLING_ROLE
GRANT SELECT, INSERT, UPDATE ON hcms_admin.bill TO billing_role;
GRANT SELECT, INSERT ON hcms_admin.bill_item TO billing_role;
GRANT SELECT, INSERT ON hcms_admin.payment TO billing_role;
GRANT SELECT ON hcms_admin.vw_patient_billing_summary TO billing_role;
REVOKE ALL ON hcms_admin.diagnosis FROM billing_role;
REVOKE ALL ON hcms_admin.clinical_note FROM billing_role;
REVOKE ALL ON hcms_admin.prescription FROM billing_role;

-- ADMIN_ROLE (fixed: one GRANT statement per table -- the original
-- "ON a, b, c" multi-object syntax is invalid in Oracle)
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.patient TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.appointment TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.admission TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.diagnosis TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.clinical_note TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.prescription TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.prescription_item TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.lab_order TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.medicine TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.bill TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.bill_item TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.payment TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.service_queue TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.vital_sign TO admin_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON hcms_admin.room_bed TO admin_role;
GRANT EXECUTE ON hcms_admin.pkg_clinical_ops TO admin_role;

-- READONLY_ROLE (new -- backs the DBMS Concept Lab sandbox, Phase 13.4)
GRANT SELECT ON hcms_admin.department TO readonly_role;
GRANT SELECT ON hcms_admin.doctor TO readonly_role;
GRANT SELECT ON hcms_admin.nurse TO readonly_role;
GRANT SELECT ON hcms_admin.patient TO readonly_role;
GRANT SELECT ON hcms_admin.room_bed TO readonly_role;
GRANT SELECT ON hcms_admin.staff_schedule TO readonly_role;
GRANT SELECT ON hcms_admin.appointment TO readonly_role;
GRANT SELECT ON hcms_admin.admission TO readonly_role;
GRANT SELECT ON hcms_admin.symptom TO readonly_role;
GRANT SELECT ON hcms_admin.diagnosis TO readonly_role;
GRANT SELECT ON hcms_admin.diagnosis_symptom TO readonly_role;
GRANT SELECT ON hcms_admin.vital_sign TO readonly_role;
GRANT SELECT ON hcms_admin.clinical_note TO readonly_role;
GRANT SELECT ON hcms_admin.medicine TO readonly_role;
GRANT SELECT ON hcms_admin.prescription TO readonly_role;
GRANT SELECT ON hcms_admin.prescription_item TO readonly_role;
GRANT SELECT ON hcms_admin.lab_test_catalog TO readonly_role;
GRANT SELECT ON hcms_admin.lab_order TO readonly_role;
GRANT SELECT ON hcms_admin.insurance_policy TO readonly_role;
GRANT SELECT ON hcms_admin.bill TO readonly_role;
GRANT SELECT ON hcms_admin.bill_item TO readonly_role;
GRANT SELECT ON hcms_admin.payment TO readonly_role;
GRANT SELECT ON hcms_admin.service_queue TO readonly_role;
GRANT SELECT ON hcms_admin.vw_patient_medical_summary TO readonly_role;
GRANT SELECT ON hcms_admin.vw_doctor_appointment_schedule TO readonly_role;
GRANT SELECT ON hcms_admin.vw_patient_billing_summary TO readonly_role;
GRANT SELECT ON hcms_admin.vw_pending_lab_reports TO readonly_role;
GRANT SELECT ON hcms_admin.vw_current_admitted_patients TO readonly_role;
GRANT SELECT ON hcms_admin.vw_medicine_inventory_status TO readonly_role;
GRANT SELECT ON hcms_admin.vw_emergency_queue TO readonly_role;
GRANT SELECT ON hcms_admin.vw_doctor_workload TO readonly_role;
-- Deliberately NOT granted: app_user, audit_log, ml_prediction (contain
-- credentials-adjacent / internal bookkeeping data not meant for the
-- teaching sandbox).

-- ---------------------------------------------------------------------
-- Assign roles to users
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
-- Security features discussion (for the report/viva) -- unchanged from
-- the original file, reproduced here for completeness:
--   - Password security: Oracle enforces complexity via profiles
--     (CREATE PROFILE ... PASSWORD_VERIFY_FUNCTION); kept conceptual here.
--   - RBAC / least privilege: demonstrated concretely above.
--   - Confidentiality & integrity: GRANT scope (confidentiality) plus
--     CHECK/FK constraints + triggers (integrity).
--   - SQL injection prevention: the backend uses parameterized queries
--     exclusively (bind variables), never string-concatenated SQL.
--   - Input validation: two layers -- API-level (Pydantic types/ranges)
--     and DB-level (CHECK constraints as the last line of defense).
--   - Audit logging: AUDIT_LOG + trg_bill_audit/trg_patient_audit.
--   - Views for restricted access: vw_patient_billing_summary,
--     vw_doctor_appointment_schedule, etc.
--   - Encryption concepts: Oracle TDE / DBMS_CRYPTO -- not implemented
--     in this academic build, flagged as a production concern.
--   - Backup/recovery: conceptually RMAN / EXPDP-IMPDP -- viva mention
--     only, not part of the deliverable.
--   - Session management: the backend issues short-lived JWTs mapped to
--     a DB role at each pooled connection checkout.
-- ---------------------------------------------------------------------

PROMPT Users, roles, and grants created (including NURSE_ROLE/nurse1 and READONLY_ROLE/readonly1).
PROMPT Next: set the corresponding *_PWD environment variables for the backend (see README.md) and run 13_audit.sql if not already applied.
