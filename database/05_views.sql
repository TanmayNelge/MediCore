-- =====================================================================
-- 05_views.sql
-- MediCore HCMS - Reporting / access-control views. Run AFTER sample data.
-- =====================================================================
-- V1 - vw_patient_medical_summary
-- One-stop read of a patient's clinical history without exposing billing.
-- Not updatable (3-table join, no key-preserved table).
CREATE OR REPLACE VIEW vw_patient_medical_summary AS
SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient_name,
       TRUNC(MONTHS_BETWEEN(SYSDATE,p.dob)/12) AS age, p.gender, p.blood_group,
       dg.disease_name, dg.severity, dg.diagnosis_date,
       doc.first_name || ' ' || doc.last_name AS diagnosed_by
FROM patient p
JOIN diagnosis dg ON dg.patient_id = p.patient_id
JOIN doctor doc ON doc.doctor_id = dg.doctor_id;
-- V2 - vw_doctor_appointment_schedule
-- Technically updatable (status, key-preserved on appointment), but writes
-- are still routed through book_appointment/cancel_appointment so triggers/
-- audit fire consistently.
CREATE OR REPLACE VIEW vw_doctor_appointment_schedule AS
SELECT d.doctor_id, d.first_name||' '||d.last_name AS doctor_name,
       a.appt_date, a.appt_time, a.status,
       p.first_name||' '||p.last_name AS patient_name
FROM doctor d JOIN appointment a ON a.doctor_id = d.doctor_id
JOIN patient p ON p.patient_id = a.patient_id;
-- V3 - vw_patient_billing_summary
-- Not updatable (aggregated). Complex multi-join/aggregate view.
CREATE OR REPLACE VIEW vw_patient_billing_summary AS
SELECT b.bill_id, b.patient_id, b.bill_date, b.status,
       SUM(bi.amount) AS total_amount,
       NVL((SELECT SUM(amount_paid) FROM payment pay WHERE pay.bill_id = b.bill_id),0) AS total_paid,
       SUM(bi.amount) - NVL((SELECT SUM(amount_paid) FROM payment pay WHERE pay.bill_id = b.bill_id),0) AS balance_due
FROM bill b JOIN bill_item bi ON bi.bill_id = b.bill_id
GROUP BY b.bill_id, b.patient_id, b.bill_date, b.status;
-- V4 - vw_pending_lab_reports
CREATE OR REPLACE VIEW vw_pending_lab_reports AS
SELECT lo.lab_order_id, p.first_name||' '||p.last_name AS patient_name,
       ltc.test_name, lo.order_date, lo.status
FROM lab_order lo JOIN patient p ON p.patient_id = lo.patient_id
JOIN lab_test_catalog ltc ON ltc.lab_test_id = lo.lab_test_id
WHERE lo.status IN ('ORDERED','SAMPLE_COLLECTED');
-- V5 - vw_current_admitted_patients
-- Updatable for simple column changes (key-preserved join anchored on
-- admission), but writes are still routed through discharge_patient.
CREATE OR REPLACE VIEW vw_current_admitted_patients AS
SELECT ad.admission_id, p.first_name||' '||p.last_name AS patient_name,
       rb.room_no, rb.bed_no, ad.admit_date, doc.first_name||' '||doc.last_name AS admitting_doctor
FROM admission ad JOIN patient p ON p.patient_id = ad.patient_id
JOIN room_bed rb ON rb.room_bed_id = ad.room_bed_id
JOIN doctor doc ON doc.doctor_id = ad.admitting_doctor_id
WHERE ad.status = 'ADMITTED';
-- V6 - vw_medicine_inventory_status
-- Updatable (single base table, no aggregation) - good candidate for
-- direct pharmacy-staff UPDATE via GRANT.
CREATE OR REPLACE VIEW vw_medicine_inventory_status AS
SELECT medicine_id, medicine_name, stock_quantity, reorder_level,
       CASE WHEN stock_quantity <= reorder_level THEN 'REORDER' ELSE 'OK' END AS stock_status
FROM medicine;
-- V7 - vw_emergency_queue
CREATE OR REPLACE VIEW vw_emergency_queue AS
SELECT queue_id, patient_id, priority_level, arrival_time, status
FROM service_queue
WHERE queue_type = 'EMERGENCY' AND status IN ('WAITING','CALLED')
ORDER BY priority_level, arrival_time;
-- V8 - vw_doctor_workload
CREATE OR REPLACE VIEW vw_doctor_workload AS
SELECT d.doctor_id, d.first_name||' '||d.last_name AS doctor_name,
       COUNT(a.appointment_id) AS total_appointments,
       SUM(CASE WHEN a.status='COMPLETED' THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN a.status='NO_SHOW' THEN 1 ELSE 0 END) AS no_shows
FROM doctor d LEFT JOIN appointment a ON a.doctor_id = d.doctor_id
GROUP BY d.doctor_id, d.first_name, d.last_name;
