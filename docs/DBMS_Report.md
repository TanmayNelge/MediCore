# MediCore HCMS — DBMS Report

Oracle XE 21c/23ai · FastAPI · React · scikit-learn

This report covers every item in the project brief. For each item it points to the file or screen that implements it.

| Brief item | Where it is implemented |
|---|---|
| 1. Entities, attributes, relationships, business rules, ER/EER → relational | §1–§3, **ER model** page, `database/01_schema.sql` |
| 2. PK / candidate / FK keys, functional dependencies, 1NF → BCNF | §4–§5, **Keys & normalization** page |
| 3. DDL, DML, joins, nested / correlated queries, aggregates, GROUP BY / HAVING, sample data | §6, `database/15_demo_queries.sql`, **DBMS concept lab**, **Reports**, `database/04_sample_data.sql` |
| 4. Views, indexes, triggers, procedures, transactions / ACID, concurrency, security / RBAC | §7–§9, `05`–`14`, `16_transactions_concurrency.sql`, live demos in **DBMS concept lab** |
| Front end: insert / search / update / delete / reports, SQL shown, ER & schema links, the Front End → SQL → DB → Result flow | §10 |
| AI / ML | §11, **AI/ML insights** page, `ml/` |

---

## 1. Entities and attributes (28 tables)

| Domain | Entity | Key attributes (PK **bold**) |
|---|---|---|
| Organisation | DEPARTMENT | **department_id**, department_name (unique), head_doctor_id, location |
| | DOCTOR | **doctor_id**, name, department_id, specialization, qualification, license_no (unique), phone, email (unique), consultation_fee, joining_date |
| | NURSE | **nurse_id**, name, department_id, license_no (unique), shift |
| | ROOM_BED | **room_bed_id**, (room_no, bed_no) unique, department_id, room_type, status, daily_rate |
| | STAFF_SCHEDULE | **schedule_id**, doctor_id, schedule_date, start_time, end_time, max_patients |
| Patient care | PATIENT | **patient_id**, name, dob, gender, blood_group, phone, email, address, city, emergency contact, registered_date |
| | INSURANCE_POLICY | **policy_id**, patient_id (unique → 1:0..1), policy_no (unique), provider, coverage, valid_until |
| | APPOINTMENT | **appointment_id**, patient_id, doctor_id, appt_date, appt_time, appt_type, status, reason, created_at |
| | ADMISSION | **admission_id**, patient_id, room_bed_id, admitting_doctor_id, admit/discharge date, status, reason |
| | SERVICE_QUEUE | **queue_id**, queue_type, queue_number, queue_date, patient_id, doctor_id, department_id, priority_level, arrival/called time, status |
| Clinical | DISEASE | **disease_code** (ICD-10 natural key), disease_name, is_chronic |
| | DIAGNOSIS | **diagnosis_id**, patient_id, doctor_id, appointment_id XOR admission_id, disease_code, severity, diagnosis_date |
| | SYMPTOM / DIAGNOSIS_SYMPTOM | **symptom_id**, symptom_name / **(diagnosis_id, symptom_id)** |
| | VITAL_SIGN | **vital_id**, patient, encounter, recorded_at, temperature, pulse, BP, SpO₂, height, weight |
| | CLINICAL_NOTE | **note_id**, patient, doctor, encounter, note_text (CLOB), created_at |
| Pharmacy & lab | MEDICINE | **medicine_id**, medicine_code (unique), name, category, unit_price, stock_quantity, reorder_level, expiry_date |
| | PRESCRIPTION / PRESCRIPTION_ITEM | **prescription_id** … / **prescription_item_id**, (prescription_id, medicine_id) unique, dosage, duration, quantity |
| | LAB_TEST_CATALOG / LAB_ORDER | **lab_test_id**, test_code (unique), price / **lab_order_id**, status, result_value, result_date |
| Finance | BILL / BILL_ITEM / PAYMENT | **bill_id**, status / **bill_item_id**, category, amount / **payment_id**, amount_paid, mode, paid_date |
| System & AI | APP_USER, AUDIT_LOG | **user_id**, username (unique), role_name, links / **audit_id**, table, operation, old/new value, user |
| | ML_MODEL_RUN | **run_id**, (model_name, model_version) unique, metrics, threshold, is_active, metrics_json |
| | ML_PREDICTION | **prediction_id**, (appointment_id, run_id) unique, prediction, probability, risk_factors |

**Derived attributes are never stored.** Age comes from `calculate_age(dob)`, BMI from `calculate_bmi`, a bill's total from `calculate_bill_total`, and its balance from `fn_bill_balance` and the views.

## 2. Relationships (cardinality)

- DEPARTMENT 1 — N DOCTOR, NURSE, ROOM_BED. DEPARTMENT N — 1 DOCTOR as head of department, a circular FK that is added with `ALTER TABLE`.
- PATIENT 1 — N APPOINTMENT, ADMISSION, DIAGNOSIS, VITAL_SIGN, CLINICAL_NOTE, PRESCRIPTION, LAB_ORDER, BILL and SERVICE_QUEUE.
- PATIENT 1 — 0..1 INSURANCE_POLICY.
- DOCTOR 1 — N APPOINTMENT, STAFF_SCHEDULE, DIAGNOSIS, PRESCRIPTION and LAB_ORDER.
- ROOM_BED 1 — N ADMISSION. At most one of them is ADMITTED at a time; this is enforced by procedure and trigger.
- DIAGNOSIS M — N SYMPTOM, through DIAGNOSIS_SYMPTOM. DISEASE 1 — N DIAGNOSIS.
- PRESCRIPTION 1 — N PRESCRIPTION_ITEM N — 1 MEDICINE (an associative entity carrying dosage and quantity).
- BILL 1 — N BILL_ITEM, and BILL 1 — N PAYMENT.
- APPOINTMENT 1 — N ML_PREDICTION (one per model run). ML_MODEL_RUN 1 — N ML_PREDICTION.
- APP_USER 1 — N AUDIT_LOG.

**EER constructs**
- **Specialisation:** STAFF ⊃ {DOCTOR, NURSE}, disjoint and partial. It is mapped one table per subclass, with no superclass table.
- **Category (union type):** APP_USER is a DOCTOR, a NURSE or a PATIENT. This is three nullable FKs with a CHECK that at most one is set.
- **Exclusive arc:** a DIAGNOSIS, VITAL_SIGN or CLINICAL_NOTE belongs to an APPOINTMENT *or* an ADMISSION (`chk_diag_one_encounter`).
- **Weak / dependent entities:** BILL_ITEM and PRESCRIPTION_ITEM use `ON DELETE CASCADE` from their owner.

## 3. Business rules and how they are enforced

| # | Rule | Mechanism |
|---|---|---|
| 1 | A doctor cannot have two appointments in the same slot, and neither can a patient | `UNIQUE (doctor_id, appt_date, appt_time)` and `UNIQUE (patient_id, …)`, plus `trg_appointment_conflict` |
| 2 | Appointments cannot be booked in the past; time must be HH24:MI | `book_appointment` (-20004/-20005), REGEXP CHECK |
| 3 | Booking always creates an OPD queue token (atomic) | `book_appointment` (one transaction, `LOCK TABLE` for token numbering) |
| 4 | A bed holds one admitted patient; bed status follows admissions and transfers | `admit_patient` (`FOR UPDATE`), `transfer_bed` (lock ordering), `trg_bed_status_update` |
| 5 | Cannot prescribe more than the stock; stock is deducted automatically | `trg_prescription_stock_check`, `trg_inventory_deduct` |
| 6 | Bill status is UNPAID → PARTIALLY_PAID → PAID, driven by payments | compound trigger `trg_bill_status_update` (avoids ORA-04091) |
| 7 | No over-payment, even by two clerks at once | `record_payment` (`SELECT … FOR UPDATE`, -20040) |
| 8 | Patients with medical or financial history cannot be deleted | `delete_patient` (-20031), FK constraints (ORA-02292) |
| 9 | A diagnosis, bill, vital, note or prescription must belong to the same patient as its encounter | 5 `*_encounter_chk` triggers → `check_encounter_patient` (-20050) |
| 10 | Every change to patients, bills, appointments and stock is audited with the real user | audit triggers + `current_app_user_id()` (SESSION_USER → APP_USER) |
| 11 | Exactly one active ML model | unique function-based index `uq_one_active_model` |
| 12 | Emergency patients are seen before routine ones; first come, first served within a priority level | `get_next_patient` (`ORDER BY priority_level, arrival_time FOR UPDATE SKIP LOCKED`) |

## 4. Keys and functional dependencies

The **Keys & normalization** page lists all 28 tables. For each one it shows the PK, candidate keys, FKs and FDs, and the normal form reached. Summary:

- **Surrogate PKs** come from sequences (`DEFAULT seq_x.NEXTVAL`). The exceptions are DISEASE, which uses the ICD-10 code as a natural key, and DIAGNOSIS_SYMPTOM, which has a composite PK.
- **Candidate (alternate) keys:**
  - department_name
  - doctor/nurse license_no and email
  - (room_no, bed_no)
  - (doctor_id, schedule_date, start_time)
  - (doctor_id, appt_date, appt_time) and (patient_id, appt_date, appt_time)
  - medicine_code, test_code, policy_no
  - insurance_policy.patient_id
  - (queue_type, queue_date, queue_number)
  - username
  - (model_name, model_version)
  - (appointment_id, run_id)
- **FDs:** every non-key attribute depends on the PK, and each candidate key determines the PK. Two FDs drove the v2 redesign:
  - `disease_code → disease_name` led to the new DISEASE table.
  - `appointment_id → patient_id`, `run_id → model_name, model_version` led to the trimmed ML_PREDICTION table.

## 5. Normalization (UNF → BCNF)

Worked example (also on the **Keys & normalization** page):

1. **UNF:** a "visit sheet" `VISIT(appointment_id, …, {disease_code, disease_name}, {medicine_code, medicine_name, unit_price, dosage, qty})` has repeating groups.
2. **1NF:** one row per (appointment, medicine) with atomic values. The partial dependencies `appointment_id → patient…` and `medicine_code → medicine_name, unit_price` remain.
3. **2NF:** split into APPOINTMENT, MEDICINE and PRESCRIPTION_ITEM. The transitive dependencies `appointment_id → doctor_id → department_id → location` and `disease_code → disease_name` remain.
4. **3NF:** split into PATIENT, DOCTOR, DEPARTMENT, DISEASE and DIAGNOSIS.
5. **BCNF:** every determinant is a candidate key. APPOINTMENT has three overlapping candidate keys and is still in BCNF. ROOM_BED is in BCNF under the "rate per bed" rule. If the hospital's rule were `room_no → room_type, daily_rate`, it would split into ROOM + BED.

**Violations found in the original schema and fixed in v2**

| Table | Problem | Fix |
|---|---|---|
| DIAGNOSIS | `disease_code → disease_name` (transitive, 3NF) | new table DISEASE; DIAGNOSIS keeps the FK only |
| ML_PREDICTION | `appointment_id → patient_id` and `(model_name, model_version)` with no registry (transitive) | patient reached via APPOINTMENT; new ML_MODEL_RUN registry, FK `run_id` |
| PATIENT | city buried inside the free-text address, so the ML had to parse it with `LIKE '%PUNE%'` (non-atomic, 1NF) | `city` column |

**Documented controlled redundancy (3NF\*).** `patient_id` is kept in DIAGNOSIS, VITAL_SIGN, CLINICAL_NOTE, PRESCRIPTION and BILL. The encounter FK is optional or exclusive, so patient_id is not always derivable, and keeping it avoids a two-way join on every patient look-up. Consistency triggers guarantee it can never disagree with the encounter. SERVICE_QUEUE.department_id is kept for department-level queues that have no doctor.

## 6. SQL coverage (requirement 3)

| Concept | Example (file / screen) |
|---|---|
| DDL (CREATE/ALTER/DROP, constraints, sequences) | `01_schema.sql`, `03_sequences.sql`, `15_demo_queries.sql` §A |
| DML (INSERT/UPDATE/DELETE/MERGE, INSERT…SELECT, RETURNING INTO) | Patients & Appointments pages, `generate_bill`, ML MERGE, `15_demo_queries.sql` §B |
| INNER / LEFT / RIGHT / FULL / SELF / CROSS / NATURAL (USING) / anti-join | DBMS lab "Joins", `15_demo_queries.sql` §C |
| Single-row, multi-row (IN, NOT IN, ANY/ALL), inline view, CTE | DBMS lab "Sub-queries", §D |
| Correlated sub-queries, EXISTS / NOT EXISTS | §E, report "Patients who frequently miss appointments", ML feature SQL |
| Aggregates, GROUP BY, HAVING, ROLLUP, CUBE, GROUPING, PIVOT | §F, reports "Revenue by department", "Collections by payment mode", "Age / gender profile" |
| Analytic functions (RANK, DENSE_RANK, LAG, NTILE, running SUM, KEEP DENSE_RANK LAST) | §G, report "Doctor workload ranking", `ml/features.py` |
| Set operations (UNION, INTERSECT, MINUS, UNION ALL) | §H, report "Insurance coverage" |
| Sample data | `04_sample_data.sql`: **28,310 rows** in every table, generated by `generate_seed_data.py` and validated against all constraints |

## 7. Views, indexes, triggers, procedures

- **14 views:**
  - medical summary
  - doctor schedule
  - billing summary
  - pending labs
  - admitted patients
  - inventory status
  - emergency queue
  - doctor workload
  - department revenue
  - outstanding bills (a view on a view)
  - patient visit history
  - lab turnaround
  - upcoming no-show risk (ML)
  - patient directory (column-level restriction)
- **Indexes:**
  - B-tree indexes on filter columns
  - every foreign key indexed, to avoid full scans and table locks on parent DML
  - a function-based `UPPER(last_name)` index for case-insensitive search
  - a unique function-based index for "one active model"
  - the leading-column rule is documented in `06_indexes.sql`
  - Explain plans can be viewed from the DBMS lab.
- **14 triggers:**
  - conflict check
  - stock check and stock deduction
  - bed status
  - 4 audit triggers
  - 5 consistency triggers
  - the compound bill-status trigger
- **17 procedures, 7 functions and 1 package** (`pkg_clinical_ops`). Each procedure is a single transaction with `RAISE_APPLICATION_ERROR` codes; the code map is in `08_procedures.sql`.

## 8. Transactions, ACID, concurrency

`database/16_transactions_concurrency.sql` contains seven two-session scenarios. The DBMS lab runs three of them live with two real Oracle connections.

| Property | Demonstration |
|---|---|
| Atomicity | `book_appointment`; SAVEPOINT / ROLLBACK TO demo; failing `add_prescription` leaves no header row |
| Consistency | constraints + triggers reject invalid states (ORA-02291, ORA-02290, -20011 …) |
| Isolation | session B does not see A's uncommitted UPDATE (READ COMMITTED + multiversion read consistency); SERIALIZABLE scenario |
| Durability | committed data survives a restart (redo log); discussed |
| Concurrency control | row locks `FOR UPDATE` (`record_payment`, `admit_patient`), `NOWAIT` / `WAIT n`, `SKIP LOCKED` (queue), `LOCK TABLE` (token numbering), lock ordering to prevent deadlock (`transfer_bed`), ORA-00060 deadlock scenario |

## 9. Security and RBAC

- 8 Oracle users and 8 roles, with least privilege. The full matrix is in `12_security_roles.sql`. The DBMS lab "RBAC matrix" runs probes on every role, and Oracle answers ALLOWED or ORA-00942 / ORA-01031.
- **Column-level privileges:** `GRANT UPDATE (status) ON appointment`.
- **View-based restriction:** `vw_patient_directory` is the only patient object the lab, pharmacy and billing roles can read.
- **Append-only audit:** even ADMIN_ROLE has SELECT only on AUDIT_LOG.
- **Password profile:** lock-out after 10 failed logins.
- **Authentication by Oracle.** The old app-side "username == password" bypass has been removed.
- **SQL-injection safety:** bind variables everywhere. The SQL console runs on a SELECT-only account (defence in depth).

## 10. Front end ↔ database

Every screen shows the SQL it executed (with bind values rendered for display) and a flow chip:
**UI → SQL → Oracle as `<oracle user>` → N rows in X ms**.

- **Insert / search / update / delete:**
  - Patients: register, search by name/phone/ID, edit via `update_patient`, delete via `delete_patient`.
  - Appointments: book, mark done / no-show, cancel, reschedule, delete.
  - Pharmacy: add medicine, fulfil prescription.
  - Billing: generate bill, record payment.
- **Reports:** 15 parameterised SQL reports with a bar chart, CSV export and print / PDF.
- **ER model and schema:** links in the sidebar and on the Dashboard. The ER model page shows Mermaid diagrams. The schema viewer is read live from the data dictionary: tables, views, indexes, triggers, PL/SQL, sequences and constraints.
- **Oracle errors** are returned with their code and a plain-language explanation, for example "FOREIGN KEY – child record found".

## 11. AI / ML — appointment no-show prediction

- **Task:** binary classification. Will a SCHEDULED appointment end as NO_SHOW? The use is prioritising reminder calls.
- **Data:** 2,606 resolved appointments (18.3 % no-shows). The label is `appointment.status`.
- **Pre-processing:** features are computed in SQL (`ml/features.py`), with no leakage because only strictly earlier and resolved visits are used:
  - age at visit
  - lead time
  - prior visits, no-shows and cancellations
  - last-visit outcome
  - days since last visit
  - insurance
  - city
  - weekday, hour, department, gender

  These go into a scikit-learn Pipeline: median imputation, scaling, and one-hot encoding of the categoricals.
- **Model selection:** a dummy baseline, logistic regression, random forest and histogram gradient boosting are compared with 5-fold stratified CV on the training period. The highest CV ROC-AUC wins.
- **Testing:** out-of-time. The model is evaluated on the most recent 20 % (522 visits) that it never saw.
- **Imbalance:** handled by threshold moving. The threshold (F1-optimal on out-of-fold predictions) is ≈ 0.23, so probabilities stay calibrated.
- **Result (shipped model):** logistic regression.

| Metric | Value |
|---|---|
| ROC-AUC (test) | 0.752 (baseline 0.50) |
| PR-AUC | 0.387 (no-skill 0.147) |
| Recall / precision / F1 | 0.49 / 0.35 / 0.41 |
| Brier score | 0.111 |
| Lift in top-20 % riskiest | 2.35× |
| Confusion matrix [[TN, FP], [FN, TP]] | [[373, 72], [39, 38]] |

- **Top features:** booking lead time, missed last visit, lives outside Pune, department, previous visits.
- **Integration:**
  - Each run is registered in ML_MODEL_RUN (atomic switch of the active model).
  - Predictions are MERGEd into ML_PREDICTION with per-appointment risk factors (occlusion explanation).
  - The view `vw_upcoming_noshow_risk` serves them, and the **AI/ML insights** page shows them along with metrics, the confusion matrix, the ROC curve, the model comparison and feature importance.
  - The page also offers live single-appointment scoring and admin-only *Retrain* and *Re-score* buttons.
- **About the data:** the historical labels come from a documented behavioural simulation (`database/generate_seed_data.py → noshow_probability`), because no real patient data can be used. The model never sees that function. It has to rediscover the pattern from the rows in Oracle, which is why its accuracy is realistic (about 0.75 AUC) rather than perfect.
