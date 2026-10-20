-- =====================================================================
-- 04_sample_data.sql
-- MediCore HCMS - Sample/seed data (representative excerpt).
-- Run AFTER 01_schema.sql. Pair with 04b_bulk_data.sql (Phase 4.7) to
-- generate full volume (60 patients, ~150 appointments, etc.) via PL/SQL.
-- =====================================================================
-- Departments
INSERT INTO department (department_name, location) VALUES ('General Medicine', 'Block A - 1F');
INSERT INTO department (department_name, location) VALUES ('Cardiology', 'Block B - 2F');
INSERT INTO department (department_name, location) VALUES ('Orthopedics', 'Block B - 1F');
INSERT INTO department (department_name, location) VALUES ('Pediatrics', 'Block A - 2F');
INSERT INTO department (department_name, location) VALUES ('Dermatology', 'Block C - 1F');
INSERT INTO department (department_name, location) VALUES ('ENT', 'Block C - 2F');
INSERT INTO department (department_name, location) VALUES ('Gynecology', 'Block A - 3F');
INSERT INTO department (department_name, location) VALUES ('Emergency', 'Block D - Ground');
-- Doctors (sample; extend the pattern for more)
INSERT INTO doctor (first_name,last_name,department_id,specialization,qualification,license_no,phone,email,consultation_fee,joining_date)
VALUES ('Ananya','Sharma',1,'Internal Medicine','MBBS, MD','LIC-GM-1001','9810000001','ananya.sharma@medicore.in',600,DATE '2019-03-14');
INSERT INTO doctor (first_name,last_name,department_id,specialization,qualification,license_no,phone,email,consultation_fee,joining_date)
VALUES ('Rohan','Verma',2,'Interventional Cardiology','MBBS, DM Cardio','LIC-CD-1002','9810000002','rohan.verma@medicore.in',1200,DATE '2016-07-01');
INSERT INTO doctor (first_name,last_name,department_id,specialization,qualification,license_no,phone,email,consultation_fee,joining_date)
VALUES ('Kavita','Iyer',3,'Joint Replacement','MBBS, MS Ortho','LIC-OR-1003','9810000003','kavita.iyer@medicore.in',900,DATE '2018-01-22');
-- ... add ~12 more doctors across the remaining departments (same pattern)
-- Nurses
INSERT INTO nurse (first_name,last_name,department_id,license_no,phone,email,shift)
VALUES ('Meena','Joshi',1,'NUR-1001','9820000001','meena.joshi@medicore.in','MORNING');
INSERT INTO nurse (first_name,last_name,department_id,license_no,phone,email,shift)
VALUES ('Farah','Khan',8,'NUR-1002','9820000002','farah.khan@medicore.in','NIGHT');
-- ... add ~8 more nurses across departments
-- Patients
INSERT INTO patient (first_name,last_name,dob,gender,blood_group,phone,email,address,emergency_contact_name,emergency_contact_phone)
VALUES ('Aarav','Mehta',DATE '1990-05-12','M','B+','9900000001','aarav.mehta@mail.com','12 MG Road, Pune','Sunita Mehta','9900000011');
INSERT INTO patient (first_name,last_name,dob,gender,blood_group,phone,email,address,emergency_contact_name,emergency_contact_phone)
VALUES ('Priya','Nair',DATE '1985-11-03','F','O+','9900000002','priya.nair@mail.com','45 Lake View, Kochi','Ramesh Nair','9900000012');
INSERT INTO patient (first_name,last_name,dob,gender,blood_group,phone,email,address,emergency_contact_name,emergency_contact_phone)
VALUES ('Vikram','Singh',DATE '1972-02-28','M','A-','9900000003','vikram.singh@mail.com','7 Civil Lines, Prayagraj','Neha Singh','9900000013');
-- ... add ~57 more patients (vary age/gender/blood group for realistic ML features);
-- or just run 04b_bulk_data.sql below to generate volume automatically
-- Medicines
INSERT INTO medicine (medicine_code,medicine_name,category,unit_price,stock_quantity,reorder_level,expiry_date)
VALUES ('MED-001','Paracetamol 500mg','Analgesic',2.50,500,50,DATE '2027-06-30');
INSERT INTO medicine (medicine_code,medicine_name,category,unit_price,stock_quantity,reorder_level,expiry_date)
VALUES ('MED-002','Amoxicillin 250mg','Antibiotic',8.00,300,40,DATE '2026-12-31');
INSERT INTO medicine (medicine_code,medicine_name,category,unit_price,stock_quantity,reorder_level,expiry_date)
VALUES ('MED-003','Atorvastatin 10mg','Statin',12.00,200,30,DATE '2027-03-31');
-- ... add ~22 more medicines
-- Room/Beds
INSERT INTO room_bed (room_no,bed_no,department_id,room_type,daily_rate) VALUES ('101','A',1,'GENERAL',1500);
INSERT INTO room_bed (room_no,bed_no,department_id,room_type,daily_rate) VALUES ('201','A',2,'ICU',6000);
INSERT INTO room_bed (room_no,bed_no,department_id,room_type,daily_rate) VALUES ('301','A',3,'PRIVATE',3500);
-- ... add ~17 more beds
-- Appointments (spans multiple days; include a realistic ~12% NO_SHOW rate for ML training)
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (1,1,DATE '2026-09-01','09:30','NEW','COMPLETED','Fever and cough');
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (2,2,DATE '2026-09-01','10:00','NEW','COMPLETED','Chest pain evaluation');
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (3,3,DATE '2026-09-02','11:15','FOLLOW_UP','NO_SHOW','Post-op knee follow-up');
-- Upcoming scheduled appointments for ML scoring
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (1,1,TRUNC(SYSDATE)+1,'10:30','FOLLOW_UP','SCHEDULED','Routine check-up');
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (2,2,TRUNC(SYSDATE)+2,'14:00','NEW','SCHEDULED','Cardiology consult');
INSERT INTO appointment (patient_id,doctor_id,appt_date,appt_time,appt_type,status,reason)
VALUES (3,3,TRUNC(SYSDATE)+3,'11:30','FOLLOW_UP','SCHEDULED','Orthopedic review');
-- ... add ~147 more appointments spread over 30 days;
-- or run 04b_bulk_data.sql below to generate volume automatically
COMMIT;
-- NOTE: This file is a representative excerpt (per the project blueprint).
-- The full dataset target is: 8 departments, 15 doctors, 10 nurses, 60 patients,
-- 20 room/beds, ~150 appointments, ~40 diagnoses, 25 medicines, ~60 prescriptions
-- with items, 12 lab test types with ~80 orders, 40 bills with items and payments,
-- and live queue entries. Use 04b_bulk_data.sql to generate that volume
-- programmatically instead of hand-typing every row.
