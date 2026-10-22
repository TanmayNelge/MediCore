-- =====================================================================
-- 15_demo_queries.sql
-- MediCore HCMS - SQL demonstration catalogue (requirement 3).
-- Every query runs on the seeded data and returns meaningful rows.
-- Run in SQL Developer / SQLcl connected as HCMS_ADMIN (or admin1 after
-- ALTER SESSION SET CURRENT_SCHEMA = HCMS_ADMIN).
-- The same queries are runnable from the web app: DBMS Concept Lab page.
-- NOT executed by install.py (read-only demo file).
-- =====================================================================
SET LINESIZE 200
SET PAGESIZE 100

-- ---------------------------------------------------------------------
-- A. DDL (Data Definition Language)
-- ---------------------------------------------------------------------
-- A1 CREATE / ALTER / DROP on a scratch table (auto-commits)
CREATE TABLE demo_ddl (id NUMBER PRIMARY KEY, note VARCHAR2(50));
ALTER TABLE demo_ddl ADD (created_on DATE DEFAULT SYSDATE);
ALTER TABLE demo_ddl MODIFY (note VARCHAR2(100) NOT NULL);
ALTER TABLE demo_ddl ADD CONSTRAINT chk_demo_note CHECK (LENGTH(note) > 2);
DROP TABLE demo_ddl PURGE;

-- ---------------------------------------------------------------------
-- B. DML (Data Manipulation Language) - each block rolled back so the
--    seed data stays intact
-- ---------------------------------------------------------------------
-- B1 INSERT (sequence fills the PK through the column DEFAULT)
INSERT INTO patient (first_name, last_name, dob, gender, blood_group, phone, address, city)
VALUES ('Demo', 'Patient', DATE '1999-01-15', 'F', 'O+', '9000000001', 'Kothrud - 411038', 'Pune');
-- B2 UPDATE (fires trg_patient_audit)
UPDATE patient SET phone = '9000000002' WHERE last_name = 'Patient' AND first_name = 'Demo';
-- B3 DELETE
DELETE FROM patient WHERE last_name = 'Patient' AND first_name = 'Demo';
-- B4 MERGE (upsert) - restock: add 100 units to low-stock items, insert a new item
MERGE INTO medicine m
USING (SELECT 'MED-046' code, 'Prednisolone 10mg Tablet' name, 100 qty FROM dual UNION ALL
       SELECT 'MED-099', 'Cough Syrup 100ml', 50 FROM dual) s
ON (m.medicine_code = s.code)
WHEN MATCHED THEN UPDATE SET m.stock_quantity = m.stock_quantity + s.qty
WHEN NOT MATCHED THEN INSERT (medicine_code, medicine_name, category, unit_price, stock_quantity)
                      VALUES (s.code, s.name, 'Antitussive', 85, s.qty);
ROLLBACK;

-- ---------------------------------------------------------------------
-- C. JOINS
-- ---------------------------------------------------------------------
-- C1 INNER JOIN (3 tables): today's appointments with doctor and department
SELECT a.appointment_id, a.appt_time, p.first_name || ' ' || p.last_name AS patient,
       'Dr. ' || d.last_name AS doctor, dep.department_name, a.status
FROM appointment a
JOIN patient p      ON p.patient_id = a.patient_id
JOIN doctor d       ON d.doctor_id = a.doctor_id
JOIN department dep ON dep.department_id = d.department_id
WHERE a.appt_date = TRUNC(SYSDATE)
ORDER BY a.appt_time;

-- C2 LEFT OUTER JOIN: every patient and their insurance (NULL = uninsured)
SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient,
       NVL(ip.provider_name, '-- self pay --') AS insurer, ip.valid_until
FROM patient p
LEFT JOIN insurance_policy ip ON ip.patient_id = p.patient_id
ORDER BY p.patient_id FETCH FIRST 15 ROWS ONLY;

-- C3 RIGHT OUTER JOIN: every bed, and who occupies it now (if anyone)
SELECT rb.room_no, rb.bed_no, rb.room_type, rb.status,
       p.first_name || ' ' || p.last_name AS current_patient
FROM admission ad
JOIN patient p ON p.patient_id = ad.patient_id AND ad.status = 'ADMITTED'
RIGHT JOIN room_bed rb ON rb.room_bed_id = ad.room_bed_id
ORDER BY rb.room_no, rb.bed_no;

-- C4 FULL OUTER JOIN: medicines vs. prescriptions in the last 30 days
--    (shows medicines never prescribed AND prescribed ones)
SELECT m.medicine_code, m.medicine_name, NVL(x.units, 0) AS units_last_30_days
FROM medicine m
FULL OUTER JOIN (SELECT pi.medicine_id, SUM(pi.quantity) AS units
                   FROM prescription_item pi JOIN prescription pr ON pr.prescription_id = pi.prescription_id
                  WHERE pr.prescribed_date >= TRUNC(SYSDATE) - 30
                  GROUP BY pi.medicine_id) x ON x.medicine_id = m.medicine_id
ORDER BY units_last_30_days;

-- C5 SELF JOIN: each department, its head and the other doctors in it
SELECT dep.department_name, 'Dr. ' || head.last_name AS head_of_department,
       'Dr. ' || colleague.first_name || ' ' || colleague.last_name AS colleague
FROM department dep
JOIN doctor head      ON head.doctor_id = dep.head_doctor_id
JOIN doctor colleague ON colleague.department_id = head.department_id
                     AND colleague.doctor_id != head.doctor_id
ORDER BY dep.department_name;

-- C6 SELF JOIN on APPOINTMENT: patients who saw two different departments on the same day
SELECT a1.patient_id, a1.appt_date, a1.doctor_id AS doctor_1, a2.doctor_id AS doctor_2
FROM appointment a1
JOIN appointment a2 ON a2.patient_id = a1.patient_id AND a2.appt_date = a1.appt_date
                   AND a2.appointment_id > a1.appointment_id;

-- C7 CROSS JOIN: doctor x weekday availability matrix skeleton
SELECT d.last_name, w.weekday
FROM doctor d
CROSS JOIN (SELECT 'MON' weekday FROM dual UNION ALL SELECT 'TUE' FROM dual UNION ALL
            SELECT 'WED' FROM dual) w
WHERE d.department_id = 2;

-- C8 NATURAL JOIN / USING
SELECT department_id, department_name, COUNT(*) AS beds
FROM room_bed JOIN department USING (department_id)
GROUP BY department_id, department_name;

-- C9 Anti-join: patients registered but never booked
SELECT p.patient_id, p.first_name, p.last_name, p.registered_date
FROM patient p
LEFT JOIN appointment a ON a.patient_id = p.patient_id
WHERE a.appointment_id IS NULL;

-- ---------------------------------------------------------------------
-- D. SUB-QUERIES
-- ---------------------------------------------------------------------
-- D1 Single-row sub-query: doctors charging more than the average fee
SELECT first_name, last_name, specialization, consultation_fee
FROM doctor
WHERE consultation_fee > (SELECT AVG(consultation_fee) FROM doctor)
ORDER BY consultation_fee DESC;

-- D2 Multi-row sub-query with IN: patients diagnosed with diabetes
SELECT patient_id, first_name, last_name
FROM patient
WHERE patient_id IN (SELECT patient_id FROM diagnosis WHERE disease_code LIKE 'E11%');

-- D3 NOT IN: medicines never prescribed
SELECT medicine_code, medicine_name FROM medicine
WHERE medicine_id NOT IN (SELECT medicine_id FROM prescription_item);

-- D4 ANY / ALL: doctors whose fee is higher than ALL pediatricians
SELECT last_name, consultation_fee FROM doctor
WHERE consultation_fee > ALL (SELECT consultation_fee FROM doctor WHERE department_id = 4);

-- D5 Inline view (sub-query in FROM): top 5 diagnoses
SELECT * FROM (
    SELECT ds.disease_name, dg.disease_code, COUNT(*) AS cases
    FROM diagnosis dg JOIN disease ds ON ds.disease_code = dg.disease_code
    GROUP BY ds.disease_name, dg.disease_code ORDER BY cases DESC
) WHERE ROWNUM <= 5;

-- D6 Scalar sub-query in SELECT: each patient's visit count
SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient,
       (SELECT COUNT(*) FROM appointment a WHERE a.patient_id = p.patient_id) AS visits
FROM patient p
ORDER BY visits DESC FETCH FIRST 10 ROWS ONLY;

-- D7 WITH clause (Common Table Expression)
WITH monthly AS (
    SELECT TRUNC(paid_date, 'MM') AS month, SUM(amount_paid) AS collected
    FROM payment GROUP BY TRUNC(paid_date, 'MM')
)
SELECT month, collected,
       collected - LAG(collected) OVER (ORDER BY month) AS change_vs_last_month
FROM monthly ORDER BY month;

-- ---------------------------------------------------------------------
-- E. CORRELATED SUB-QUERIES (inner query references the outer row)
-- ---------------------------------------------------------------------
-- E1 Doctors whose fee is above the average of THEIR OWN department
SELECT d.last_name, d.department_id, d.consultation_fee
FROM doctor d
WHERE d.consultation_fee > (SELECT AVG(d2.consultation_fee) FROM doctor d2
                             WHERE d2.department_id = d.department_id);

-- E2 EXISTS: patients with at least one unpaid / partially paid bill
SELECT p.patient_id, p.first_name, p.last_name, p.phone
FROM patient p
WHERE EXISTS (SELECT 1 FROM bill b WHERE b.patient_id = p.patient_id
                AND b.status IN ('UNPAID', 'PARTIALLY_PAID'));

-- E3 NOT EXISTS: patients who have never missed an appointment (and had >= 5 visits)
SELECT p.patient_id, p.first_name, p.last_name
FROM patient p
WHERE NOT EXISTS (SELECT 1 FROM appointment a WHERE a.patient_id = p.patient_id AND a.status = 'NO_SHOW')
  AND (SELECT COUNT(*) FROM appointment a WHERE a.patient_id = p.patient_id AND a.status = 'COMPLETED') >= 5;

-- E4 Each patient's MOST RECENT vital signs (correlated MAX)
SELECT v.patient_id, v.recorded_at, v.systolic_bp, v.diastolic_bp, v.pulse_rate
FROM vital_sign v
WHERE v.recorded_at = (SELECT MAX(v2.recorded_at) FROM vital_sign v2 WHERE v2.patient_id = v.patient_id)
FETCH FIRST 15 ROWS ONLY;

-- E5 Correlated UPDATE (rolled back): flag fees to department maximum
UPDATE doctor d SET consultation_fee = (SELECT MAX(consultation_fee) FROM doctor d2
                                         WHERE d2.department_id = d.department_id)
WHERE department_id = 10;
ROLLBACK;

-- ---------------------------------------------------------------------
-- F. AGGREGATES, GROUP BY, HAVING
-- ---------------------------------------------------------------------
-- F1 Aggregate functions
SELECT COUNT(*) AS bills, SUM(amount) AS total_billed, ROUND(AVG(amount), 2) AS avg_item,
       MIN(amount) AS cheapest_item, MAX(amount) AS costliest_item
FROM bill_item;

-- F2 GROUP BY: appointment outcomes per department
SELECT dep.department_name,
       COUNT(*)                                                AS appointments,
       SUM(CASE WHEN a.status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN a.status = 'NO_SHOW'   THEN 1 ELSE 0 END) AS no_shows,
       ROUND(100 * SUM(CASE WHEN a.status = 'NO_SHOW' THEN 1 ELSE 0 END) /
             NULLIF(SUM(CASE WHEN a.status IN ('COMPLETED','NO_SHOW') THEN 1 ELSE 0 END), 0), 1) AS no_show_pct
FROM appointment a
JOIN doctor d       ON d.doctor_id = a.doctor_id
JOIN department dep ON dep.department_id = d.department_id
GROUP BY dep.department_name
ORDER BY no_show_pct DESC;

-- F3 HAVING: diseases seen more than 40 times
SELECT ds.disease_name, COUNT(*) AS cases
FROM diagnosis dg JOIN disease ds ON ds.disease_code = dg.disease_code
GROUP BY ds.disease_name
HAVING COUNT(*) > 40
ORDER BY cases DESC;

-- F4 WHERE + GROUP BY + HAVING together: patients with >= 3 no-shows in the last year
SELECT patient_id, COUNT(*) AS no_shows
FROM appointment
WHERE status = 'NO_SHOW' AND appt_date >= ADD_MONTHS(TRUNC(SYSDATE), -12)
GROUP BY patient_id
HAVING COUNT(*) >= 3
ORDER BY no_shows DESC;

-- F5 ROLLUP: revenue per payment mode per month with sub-totals and grand total
SELECT TO_CHAR(TRUNC(paid_date, 'MM'), 'YYYY-MM') AS month, payment_mode, SUM(amount_paid) AS collected
FROM payment
WHERE paid_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -2)
GROUP BY ROLLUP (TRUNC(paid_date, 'MM'), payment_mode)
ORDER BY 1, 2;

-- F6 CUBE + GROUPING(): bill items by category x status
SELECT DECODE(GROUPING(bi.item_category), 1, '** ALL **', bi.item_category) AS category,
       DECODE(GROUPING(b.status), 1, '** ALL **', b.status) AS bill_status,
       SUM(bi.amount) AS amount
FROM bill_item bi JOIN bill b ON b.bill_id = bi.bill_id
GROUP BY CUBE (bi.item_category, b.status);

-- ---------------------------------------------------------------------
-- G. ANALYTIC (WINDOW) FUNCTIONS
-- ---------------------------------------------------------------------
-- G1 RANK / DENSE_RANK: busiest doctors per department
SELECT * FROM (
    SELECT dep.department_name, d.last_name, COUNT(*) AS completed_visits,
           DENSE_RANK() OVER (PARTITION BY dep.department_name ORDER BY COUNT(*) DESC) AS rnk
    FROM appointment a JOIN doctor d ON d.doctor_id = a.doctor_id
    JOIN department dep ON dep.department_id = d.department_id
    WHERE a.status = 'COMPLETED'
    GROUP BY dep.department_name, d.last_name
) WHERE rnk = 1;

-- G2 Running total of collections (SUM() OVER ORDER BY)
SELECT paid_date, SUM(amount_paid) AS day_total,
       SUM(SUM(amount_paid)) OVER (ORDER BY paid_date) AS running_total
FROM payment
WHERE paid_date >= TRUNC(SYSDATE) - 14
GROUP BY paid_date ORDER BY paid_date;

-- G3 LAG: gap in days between consecutive visits of each patient
SELECT patient_id, appt_date,
       appt_date - LAG(appt_date) OVER (PARTITION BY patient_id ORDER BY appt_date) AS days_since_previous
FROM appointment WHERE status = 'COMPLETED' AND patient_id <= 5
ORDER BY patient_id, appt_date;

-- G4 NTILE: split patients into 4 spending quartiles
SELECT patient_id, total_spent, NTILE(4) OVER (ORDER BY total_spent DESC) AS spend_quartile
FROM (SELECT b.patient_id, SUM(bi.amount) AS total_spent
        FROM bill b JOIN bill_item bi ON bi.bill_id = b.bill_id GROUP BY b.patient_id)
FETCH FIRST 20 ROWS ONLY;

-- ---------------------------------------------------------------------
-- H. SET OPERATIONS
-- ---------------------------------------------------------------------
-- H1 UNION: everyone working in Emergency (doctors and nurses)
SELECT 'DOCTOR' AS staff_type, first_name, last_name FROM doctor WHERE department_id = 8
UNION
SELECT 'NURSE', first_name, last_name FROM nurse WHERE department_id = 8;

-- H2 INTERSECT: patients who were BOTH admitted and seen in OPD
SELECT patient_id FROM admission
INTERSECT
SELECT patient_id FROM appointment WHERE status = 'COMPLETED';

-- H3 MINUS: patients with an upcoming appointment but no insurance
SELECT patient_id FROM appointment WHERE status = 'SCHEDULED' AND appt_date > TRUNC(SYSDATE)
MINUS
SELECT patient_id FROM insurance_policy;

-- ---------------------------------------------------------------------
-- I. VIEWS, FUNCTIONS, PROCEDURES IN ACTION
-- ---------------------------------------------------------------------
SELECT * FROM vw_department_revenue WHERE bill_month >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1);
SELECT * FROM vw_outstanding_bills ORDER BY days_outstanding DESC FETCH FIRST 10 ROWS ONLY;
SELECT * FROM vw_upcoming_noshow_risk WHERE risk_band = 'HIGH' ORDER BY probability DESC;
SELECT patient_id, calculate_age(dob) AS age, fn_patient_no_show_rate(patient_id) AS no_show_rate
FROM patient WHERE ROWNUM <= 10;
SELECT bill_id, calculate_bill_total(bill_id) AS total, fn_bill_balance(bill_id) AS balance
FROM bill WHERE status = 'PARTIALLY_PAID' AND ROWNUM <= 10;

-- ---------------------------------------------------------------------
-- J. HIERARCHICAL / MISC
-- ---------------------------------------------------------------------
-- J1 CASE + date functions: age groups
SELECT CASE WHEN calculate_age(dob) < 13 THEN '0-12 child'
            WHEN calculate_age(dob) < 20 THEN '13-19 teen'
            WHEN calculate_age(dob) < 60 THEN '20-59 adult'
            ELSE '60+ senior' END AS age_group,
       COUNT(*) AS patients
FROM patient GROUP BY CASE WHEN calculate_age(dob) < 13 THEN '0-12 child'
            WHEN calculate_age(dob) < 20 THEN '13-19 teen'
            WHEN calculate_age(dob) < 60 THEN '20-59 adult'
            ELSE '60+ senior' END
ORDER BY 1;

-- J2 LISTAGG: symptoms recorded per diagnosis
SELECT dg.diagnosis_id, d.disease_name,
       LISTAGG(s.symptom_name, ', ') WITHIN GROUP (ORDER BY s.symptom_name) AS symptoms
FROM diagnosis dg
JOIN disease d            ON d.disease_code = dg.disease_code
JOIN diagnosis_symptom ds ON ds.diagnosis_id = dg.diagnosis_id
JOIN symptom s            ON s.symptom_id = ds.symptom_id
GROUP BY dg.diagnosis_id, d.disease_name
FETCH FIRST 10 ROWS ONLY;
