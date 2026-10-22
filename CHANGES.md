# MediCore HCMS v2: audit, changes and how to run it

## 1. Requirement check (before → after)

| Requirement | Before (what was in the zip) | Now |
|---|---|---|
| Entities, relationships, business rules, ER/EER → relational | ER diagram page existed; no business-rule list or EER discussion | Business rules, EER constructs and mapping rules in `docs/DBMS_Report.md` and on the **Keys & normalization** page; ER page updated to 28 tables |
| PK / CK / FK, FDs, normalization to 3NF/BCNF | Only one sentence ("the schema is in 3NF"); **3 real violations** in the schema | Per-table keys and FDs for all 28 tables, UNF→BCNF walk-through, violations **fixed** (new `DISEASE` table, `ML_MODEL_RUN` registry, `patient.city`) |
| DDL / DML, joins, nested and correlated queries, GROUP BY / HAVING, **realistic sample data** | Few demo queries; **sample data was a 3-row placeholder** (see §2) | 28,310 realistic rows; `15_demo_queries.sql` (54 statements: every join type, sub-queries, correlated, set ops, ROLLUP/CUBE/PIVOT, window functions); 37 concepts (31 runnable) in the DBMS lab |
| Views, indexes, triggers, procedures | Present (8 views, 6 triggers, 5 procedures) | 14 views, FK and function-based indexes, 14 triggers (audit with real user, consistency, bed transfer), 17 procedures (update/delete/cancel/reschedule/payment/transfer) |
| Transactions, ACID, concurrency | Mentioned in comments only | `16_transactions_concurrency.sql` (7 two-session scenarios) plus **live demos** in the app (SAVEPOINT, atomic procedure, two-session isolation / locks / SKIP LOCKED) |
| Security / RBAC | Roles existed but **grants were broken** (see §4) | Rewritten grant matrix, column-level privilege, view-based restriction, append-only audit, password profile, **live RBAC matrix** demo |
| Front end: insert / search / update / delete / reports | Insert and search only; **no update, no delete**; 2 reports | Full CRUD (patients, appointments, medicines, prescriptions, payments), 15 reports with chart, CSV and print |
| SQL shown, Front end → SQL → DB → result | SQL panel existed | SQL panel now shows **"UI → SQL → Oracle as <user> → N rows in X ms"**; Oracle errors shown with code and meaning |
| Button to view ER / schema | Sidebar links | Sidebar plus an "Explore the database" panel on the Dashboard; schema viewer now also lists views, indexes, triggers, PL/SQL, sequences and constraints |
| AI/ML: preprocessing, model selection, training, testing, evaluation, integration | Pipeline existed but **learned from random labels** (see §3) | Rebuilt pipeline (SQL features, 4 models, CV, out-of-time test, calibrated threshold, explanations); model registry table; live scoring; retrain from the UI |

## 2. Fake / placeholder data found

1. **`04_sample_data.sql` was an "excerpt".**
   - It contained 3 doctors, 2 nurses, 3 patients, 3 medicines, 3 beds and 6 appointments.
   - It had comments such as `-- ... add ~57 more patients` instead of real rows.
   - **0 rows** in diagnosis, symptom, vital_sign, clinical_note, prescription, lab_test_catalog, lab_order, insurance_policy, bill, bill_item, payment, staff_schedule, service_queue and app_user.
   - Most pages and reports were empty.
2. **`04b_bulk_data.sql` did not compile.** The first loop's `BEGIN … EXCEPTION` block had no `END;`, so the whole PL/SQL block failed.
3. **Its labels were random.** `status := CASE WHEN DBMS_RANDOM.VALUE < 0.12 THEN 'NO_SHOW' …` meant whether a patient missed a visit had nothing to do with any patient or appointment attribute. No model can learn from that.
4. **`created_at` was always the insert time**, so `lead_time_days = appt_date − created_at` was negative for every past visit and was clipped to 0. The feature was constant.
5. `run_pipeline.py --demo` trained on numbers generated in Python and **overwrote the real `no_show_model.joblib`**.

**Replaced by:** `database/generate_seed_data.py` → `04_sample_data.sql`.
- Deterministic (seed 2026) and validated against every PK, FK, UNIQUE and CHECK rule before writing.
- 28,310 rows across all 28 tables, with an Indian hospital context: Pune areas, ICD-10 codes, Indian generic medicines, INR prices, insurers including PM-JAY / CGHS.
- Bill statuses agree with payments and bed statuses agree with admissions.
- Dates are relative to the install week, so "today", the live queue and upcoming visits always exist.
- No-show labels follow a **documented behavioural model**: lead time, past no-shows, age, weekday, hour, new vs follow-up, insurance, out-of-town, department, plus a hidden per-patient reliability. The ML model has to rediscover this from the data.

## 3. ML: was it done, and do you need a new model?

The pipeline existed, but **the shipped model was not valid** and has been replaced:

| Problem in the old model | Fix |
|---|---|
| Trained on random labels; test set of only 36 rows (precision 0.22, AUC 0.67 = noise) | 2,606 labelled visits with real signal; out-of-time test on the latest 522 |
| `department_id` used as a number (1–8) | one-hot encoding inside an sklearn `Pipeline` |
| Model chosen by **recall** (a model that flags everyone wins) | chosen by 5-fold CV ROC-AUC; a dummy baseline is included for comparison |
| `class_weight='balanced'` + threshold 0.5 → probabilities inflated | natural class balance (calibrated probabilities) + F1-optimal threshold (≈0.23) |
| Prior-visit counts included cancelled / future visits; lead time always 0 | only strictly-earlier **resolved** visits; real booking timestamps |
| `pd.read_sql` + Python-side feature code duplicated for scoring | all features in **one SQL statement** (`ml/features.py`), reused for training, batch and live scoring |

**New model (shipped `ml/no_show_model.joblib`):** logistic regression, selected over random forest, gradient boosting and the dummy baseline.

| Metric (out-of-time test) | Value |
|---|---|
| ROC-AUC | 0.75 (baseline 0.50) |
| PR-AUC | 0.39 (no-skill 0.15) |
| Recall / precision / F1 | 0.49 / 0.35 / 0.41 |
| Lift in the top-20 % riskiest | 2.35× |

Top drivers: booking lead time, missed last visit, lives outside Pune, department.

**Do you need a newer model?** Not a different algorithm: logistic regression is accurate enough here, easy to explain in a viva, and gradient boosting / random forest are only about 0.01 AUC apart. But you **must retrain on your own database**, which takes about 15 seconds:
- run `.\4_run_ml.ps1`, or
- press **Retrain model** on the AI/ML page as `admin1`.

Retraining registers the run in `ML_MODEL_RUN` and scores the upcoming appointments. (The shipped .joblib was trained here with scikit-learn 1.9. If your scikit-learn version differs, retraining avoids any pickle-version warning.)

## 4. Other bugs fixed

| Bug | Effect | Fix |
|---|---|---|
| Sidebar compared `ADMIN` with `admin` | **Every role-restricted page was hidden for every user** | `frontend/src/lib/roles.js` maps Oracle roles to UI roles |
| ADMIN_ROLE had no grant on DOCTOR, DEPARTMENT, ML tables or most procedures | admin1: ORA-00942 on doctor lists; booking failed; **ML pipeline (runs as admin1) failed** | grants generated from the data dictionary |
| READONLY_ROLE had no grant on `ML_PREDICTION` | **AI/ML page always errored** | readonly gets SELECT on every table/view except APP_USER and AUDIT_LOG |
| LAB / PHARMACY / BILLING / RECEPTIONIST / NURSE missing grants their screens need | lookups and actions failed | complete matrix in `12_security_roles.sql` |
| Login accepted any `username == password` **without asking Oracle** | bypassed DB authentication | every login verified by Oracle; JWT now expires (8 h); password/lock-out profile |
| Oracle errors returned as bare HTTP 500 | UI could not show why the DB refused | global handler → readable message + ORA code |
| `trg_bed_status_update` marked a bed OCCUPIED when inserting an already-DISCHARGED admission | wrong bed status | fixed; also handles bed transfers |
| `book_appointment` queue token = `MAX()+1` race | duplicate token under concurrency | `LOCK TABLE … SHARE ROW EXCLUSIVE` (documented) |
| Payments inserted directly | two clerks could over-pay a bill | `record_payment` with `SELECT … FOR UPDATE` + balance check |
| ADMIN_ROLE had no grant at all on `AUDIT_LOG` | audit trail not viewable in the app | SELECT only: the audit log is append-only even for admins |

## 5. Changed and new files

Copy these over your project (same paths). Everything else is unchanged.

**Root**
- `README.md` (modified): v2 notes, counts, steps 5–6
- `CHANGES.md` (new): this file
- `docs/DBMS_Report.md` (new): full report (entities, relationships, business rules, keys, FDs, normalization, SQL coverage, ACID, RBAC, ML)
- `4_run_ml.ps1` (modified): installs ML requirements, `--predict-only` and `--report`
- `5_reseed_data.ps1` (new): wipe and reload only the sample data

**database/**
- `01_schema.sql` (modified): DISEASE, ML_MODEL_RUN, normalised ML_PREDICTION, patient.city, time-format CHECKs, READONLY role value, one-active-model index
- `03_sequences.sql` (modified): `seq_model_run_id`
- `04_sample_data.sql` (**regenerated**): 28,310 rows (≈5 MB)
- `04b_bulk_data.sql` (rewritten): compiles; optional booster that books future visits via `book_appointment`
- `05_views.sql` (modified): +6 views
- `06_indexes.sql` (modified): FK indexes, function-based index, leading-column notes
- `07_functions.sql` (modified): `current_app_user_id`, `fn_patient_no_show_rate`, `fn_bill_balance`
- `08_procedures.sql` (rewritten): +`transfer_bed`, `record_payment`, `update_patient`, `delete_patient`, `cancel_appointment`, `reschedule_appointment`, `check_encounter_patient`; validation and error-code map
- `10_triggers.sql` (rewritten): fixed bed trigger; audit with user and DELETE; appointment / stock audit; 5 consistency triggers
- `12_security_roles.sql` (rewritten): profile, complete grant matrix, column-level privileges
- `13_audit.sql` (modified): audit report queries
- `15_demo_queries.sql` (new): SQL catalogue for requirement 3
- `16_transactions_concurrency.sql` (new): ACID and two-session concurrency scenarios
- `generate_seed_data.py` (new): the data generator (`python generate_seed_data.py` rewrites 04)
- `install.py` (modified): new order, `--reseed`, `--with-bulk`, object/row report, schema recompile
- `run_all.sql` (modified): SQL*Plus order

**backend/**
- `requirements.txt` (modified)
- `app/main.py` (modified): Oracle error handler
- `app/auth/jwt.py` (modified): expiry, `require_roles`
- `app/routers/auth.py` (rewritten): Oracle-verified login
- `app/db/helpers.py`, `app/db/session.py` (rewritten): timing / db_user metadata, admin connection, rollback on release
- Routers:
  - `patients.py`: list/search/detail/insert/**update/delete**
  - `appointments.py`: filters, status, cancel, reschedule, delete
  - `billing.py`: outstanding, items, `record_payment`
  - `admissions.py`: bed board, transfer
  - `pharmacy.py`: add/delete medicine, fulfil
  - `clinical.py`: diseases, diagnosis by code
  - `queue.py`: today
  - `reports.py`: 15-report catalogue
  - `dbms_lab.py`: 37 concepts, console, explain, 4 live demos
  - `ml_insights.py`: registry, live score, rescore, retrain
  - `schema.py`: DB objects

**ml/**
- `features.py` (new): feature SQL
- `extract.py`, `train.py`, `evaluate.py`, `predict_and_store.py`, `run_pipeline.py` (rewritten)
- `requirements.txt` (modified)
- `no_show_model.joblib` (retrained)

**frontend/src/**
- `App.jsx`, `Layout.jsx` (modified)
- `lib/roles.js`, `components/Modal.jsx`, `components/ui.js` (new)
- `components/SqlPanel.jsx` (modified)
- `pages/NormalizationPage.jsx` (new)
- Pages: Patients, Appointments, Billing, Reports, MlInsights, DbmsLab (rewritten); Dashboard, Pharmacy, SchemaViewer, ErModel (modified)

> `frontend/dist/` is an old build and was not rebuilt. Use `npm run dev` (3_start_frontend.ps1), or run `npm run build` once.

## 6. Install and seed

Prerequisite: Oracle XE running (e.g. Docker container `oracle-xe`, service `XEPDB1`), Python 3.10+, Node 18+.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\1_install_database.ps1 -SystemPassword <your SYSTEM password>   # drops + rebuilds everything, loads 28k rows (1-3 min)
.\2_start_backend.ps1                                             # http://127.0.0.1:8000  (Swagger: /docs)
.\3_start_frontend.ps1                                            # http://localhost:5173
.\4_run_ml.ps1                                                    # train + register + score (≈15 s)
```

The installer prints one line per file (`ok / failed`), then `tables=28 … invalid objects=0` and the row count of every table. If any line starts with `!`, send that output.

- **Re-seed only the data** (keeps users and grants): `.\5_reseed_data.ps1`, then `.\4_run_ml.ps1`.
- **Regenerate the SQL file** (e.g. change patient count or no-show rules): `python database\generate_seed_data.py`.
- **Without PowerShell:** `python database/install.py --dsn localhost:1521/XEPDB1 --system-password <pwd>`, or in SQL*Plus as HCMS_ADMIN run `@run_all.sql`, then `@12_security_roles.sql` as SYSTEM.

## 7. How to see and access the database

**A. Inside the app** (log in as `admin1` / `admin1` to see everything)

| Page | What you see |
|---|---|
| Dashboard → *Explore the database* | links to everything below |
| ER model | Mermaid ER diagrams (master + per domain), cardinalities |
| Schema viewer | tables/columns/PK/FK + views, indexes, triggers, procedures, sequences, constraints, live from the data dictionary |
| Keys & normalization | PK/CK/FK and FDs of all 28 tables, UNF → BCNF |
| DBMS concept lab | SQL console (any SELECT, runs as `readonly1`), *Explain plan*, 37 concepts, ACID / concurrency demos, RBAC matrix |
| Reports | 15 SQL reports + CSV + print |
| Patients / Appointments / Billing / Pharmacy | insert, search, update, delete; every action shows its SQL |
| AI/ML insights | metrics, confusion matrix, ROC, model comparison, risk list, live scoring, retrain |

**B. SQL Developer / VS Code ("Oracle SQL Developer Extension")**: new connection

| Field | Value |
|---|---|
| Host / Port | `localhost` / `1521` |
| Service name | `XEPDB1` |
| User / Password (schema owner, sees and can change everything) | `hcms_admin` / `HcmsAdmin_123` |
| Role accounts (to show RBAC) | `doctor1/doctor1`, `receptionist1/receptionist1`, `readonly1/readonly1`, `admin1/admin1` … then run `ALTER SESSION SET CURRENT_SCHEMA = HCMS_ADMIN;` |

Open `database/15_demo_queries.sql` or `16_transactions_concurrency.sql` there and run statement by statement (Ctrl+Enter). For the concurrency scenarios open two worksheets.

**C. Command line inside Docker**
```powershell
docker exec -it oracle-xe sqlplus hcms_admin/HcmsAdmin_123@localhost:1521/XEPDB1
SQL> SELECT table_name, num_rows FROM user_tables ORDER BY 1;
SQL> SELECT * FROM vw_upcoming_noshow_risk WHERE risk_band = 'HIGH';
```

**D. API**: http://127.0.0.1:8000/docs (Swagger). Authorize with a token from `/auth/login`.

## 8. Suggested viva demo flow (≈10 min)

1. **Dashboard** → *ER model* → *Keys & normalization* (show the DISEASE fix).
2. **Patients**: register a patient → edit the phone number → open *Reports → Audit trail* to see the old and new values recorded with `admin1`.
3. **Patients**: try to delete a patient with history → ORA-20031. Delete the one you just created → success.
4. **Appointments**: book the same doctor/slot twice → refused. Mark one *Done*, then *Billing → Generate bill* → *Record payment*: the trigger flips the status to PAID.
5. **DBMS lab**: run *INNER/LEFT/SELF JOIN*, *Correlated*, *HAVING*, *ROLLUP*, then *Explain plan* on `SELECT * FROM patient WHERE UPPER(last_name) LIKE 'PAT%'` (function-based index).
6. **DBMS lab demos**: *SAVEPOINT*, *Two sessions* (no dirty read, lock wait, SKIP LOCKED), *RBAC matrix*.
7. **Reports**: Revenue by department (ROLLUP) and No-show by department (HAVING) → CSV / Print.
8. **AI/ML insights**: metrics and why accuracy is misleading, confusion matrix, model comparison → *Explain* a high-risk patient → *Retrain*.

## 9. What was and was not verified here

- **Verified in this environment:**
  - The data generator's PK/FK/UNIQUE/CHECK validation.
  - The complete ML pipeline (train, CV, evaluate, explain, score) on the generated data.
  - Every Python file compiles; the backend imports cleanly and registers 76 routes.
  - Every JSX file parses with no undefined identifiers.
- **Not executed:** a live Oracle instance could not be started in this sandbox, so the SQL/PL-SQL was not run end-to-end here. It was written for Oracle 21c/23ai and reviewed statement by statement. The installer reports any failing statement, invalid object or wrong row count immediately. If something fails on your machine, send the `!` lines.
- **Frontend build:** `npm run build` could not be run here (no npm registry access). Run `npm install` once as usual.
