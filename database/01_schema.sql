-- =====================================================================
-- 01_schema.sql
-- MediCore HCMS - Core relational schema (26 tables), Oracle 21c/23ai XE
-- Run order: 03_sequences.sql -> 01_schema.sql -> 04_sample_data.sql -> ...
-- =====================================================================
-- =========================================================
-- DEPARTMENT
-- =========================================================
CREATE TABLE department (
    department_id     NUMBER          DEFAULT seq_department_id.NEXTVAL PRIMARY KEY,
    department_name   VARCHAR2(80)    NOT NULL UNIQUE,
    head_doctor_id     NUMBER,                          -- FK added later (circular w/ DOCTOR)
    location           VARCHAR2(100),
    created_at          DATE            DEFAULT SYSDATE NOT NULL
);
-- =========================================================
-- DOCTOR
-- =========================================================
CREATE TABLE doctor (
    doctor_id          NUMBER          DEFAULT seq_doctor_id.NEXTVAL PRIMARY KEY,
     first_name          VARCHAR2(50)     NOT NULL,
     last_name           VARCHAR2(50)     NOT NULL,
     department_id       NUMBER           NOT NULL,
     specialization       VARCHAR2(80)     NOT NULL,
     qualification         VARCHAR2(120),
     license_no           VARCHAR2(30)     NOT NULL UNIQUE,
     phone                VARCHAR2(15)     NOT NULL,
     email                VARCHAR2(100)    UNIQUE,
     consultation_fee      NUMBER(8,2)      NOT NULL CHECK (consultation_fee >= 0),
     joining_date          DATE             DEFAULT SYSDATE NOT NULL,
     CONSTRAINT fk_doctor_dept FOREIGN KEY (department_id)
         REFERENCES department(department_id)
);
ALTER TABLE department
    ADD CONSTRAINT fk_dept_head FOREIGN KEY (head_doctor_id)
        REFERENCES doctor(doctor_id);
-- =========================================================
-- NURSE
-- =========================================================
CREATE TABLE nurse (
    nurse_id             NUMBER          DEFAULT seq_nurse_id.NEXTVAL PRIMARY KEY,
    first_name           VARCHAR2(50)    NOT NULL,
    last_name            VARCHAR2(50)    NOT NULL,
    department_id        NUMBER          NOT NULL,
    license_no           VARCHAR2(30)    NOT NULL UNIQUE,
    phone                 VARCHAR2(15)    NOT NULL,
    email                 VARCHAR2(100)   UNIQUE,
    shift                VARCHAR2(10)    CHECK (shift IN ('MORNING','EVENING','NIGHT')),
    joining_date          DATE            DEFAULT SYSDATE NOT NULL,
    CONSTRAINT fk_nurse_dept FOREIGN KEY (department_id)
         REFERENCES department(department_id)
);
-- =========================================================
-- PATIENT
-- =========================================================
CREATE TABLE patient (
    patient_id          NUMBER          DEFAULT seq_patient_id.NEXTVAL PRIMARY KEY,
    first_name          VARCHAR2(50)    NOT NULL,
    last_name           VARCHAR2(50)    NOT NULL,
    dob                  DATE             NOT NULL,
    gender               CHAR(1)          NOT NULL CHECK (gender IN ('M','F','O')),
    blood_group          VARCHAR2(5)      CHECK (blood_group IN
                            ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    phone                VARCHAR2(15)     NOT NULL,
    email                VARCHAR2(100)    UNIQUE,
    address              VARCHAR2(200),
    emergency_contact_name VARCHAR2(100),
    emergency_contact_phone VARCHAR2(15),
    registered_date      DATE             DEFAULT SYSDATE NOT NULL
);
-- =========================================================
-- ROOM_BED
-- =========================================================
CREATE TABLE room_bed (
    room_bed_id         NUMBER          DEFAULT seq_room_bed_id.NEXTVAL PRIMARY KEY,
    room_no              VARCHAR2(10)    NOT NULL,
    bed_no                VARCHAR2(10)    NOT NULL,
    department_id        NUMBER          NOT NULL,
    room_type             VARCHAR2(20)    CHECK (room_type IN ('GENERAL','PRIVATE','ICU','EMERGENCY')),
    status                VARCHAR2(15)    DEFAULT 'AVAILABLE' NOT NULL
                            CHECK (status IN ('AVAILABLE','OCCUPIED','MAINTENANCE')),
    daily_rate            NUMBER(8,2)     NOT NULL CHECK (daily_rate >= 0),
    CONSTRAINT uq_room_bed UNIQUE (room_no, bed_no),
    CONSTRAINT fk_roombed_dept FOREIGN KEY (department_id)
        REFERENCES department(department_id)
);
-- =========================================================
-- STAFF_SCHEDULE
-- =========================================================
CREATE TABLE staff_schedule (
    schedule_id          NUMBER          DEFAULT seq_schedule_id.NEXTVAL PRIMARY KEY,
    doctor_id             NUMBER          NOT NULL,
    schedule_date         DATE            NOT NULL,
    start_time             VARCHAR2(5)     NOT NULL,    -- 'HH24:MI'
    end_time               VARCHAR2(5)     NOT NULL,
    max_patients            NUMBER(3)       DEFAULT 20 CHECK (max_patients > 0),
    CONSTRAINT uq_doctor_slot UNIQUE (doctor_id, schedule_date, start_time),
    CONSTRAINT fk_schedule_doctor FOREIGN KEY (doctor_id)
        REFERENCES doctor(doctor_id) ON DELETE CASCADE,
    CONSTRAINT chk_schedule_times CHECK (end_time > start_time)
);
-- =========================================================
-- APPOINTMENT
-- =========================================================
CREATE TABLE appointment (
    appointment_id       NUMBER           DEFAULT seq_appointment_id.NEXTVAL PRIMARY KEY,
    patient_id             NUMBER           NOT NULL,
    doctor_id               NUMBER           NOT NULL,
    appt_date               DATE             NOT NULL,
    appt_time                VARCHAR2(5)      NOT NULL,   -- 'HH24:MI'
    appt_type                 VARCHAR2(15)     DEFAULT 'NEW' CHECK (appt_type IN ('NEW','FOLLOW_UP')),
    status                     VARCHAR2(15)     DEFAULT 'SCHEDULED' NOT NULL
                                  CHECK (status IN ('SCHEDULED','COMPLETED','CANCELLED','NO_SHOW')),
    reason                     VARCHAR2(200),
    created_at                   TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT uq_doctor_timeslot UNIQUE (doctor_id, appt_date, appt_time),
    CONSTRAINT uq_patient_timeslot UNIQUE (patient_id, appt_date, appt_time),
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_appt_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id)
);
-- =========================================================
-- ADMISSION
-- =========================================================
CREATE TABLE admission (
    admission_id          NUMBER            DEFAULT seq_admission_id.NEXTVAL PRIMARY KEY,
    patient_id               NUMBER           NOT NULL,
    room_bed_id               NUMBER           NOT NULL,
    admitting_doctor_id        NUMBER            NOT NULL,
    admit_date                  DATE              DEFAULT SYSDATE NOT NULL,
    discharge_date                DATE,
    status                          VARCHAR2(10)     DEFAULT 'ADMITTED' NOT NULL
                                      CHECK (status IN ('ADMITTED','DISCHARGED')),
    admission_reason                 VARCHAR2(200),
    CONSTRAINT fk_admission_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_admission_bed       FOREIGN KEY (room_bed_id) REFERENCES room_bed(room_bed_id),
    CONSTRAINT fk_admission_doctor FOREIGN KEY (admitting_doctor_id) REFERENCES doctor(doctor_id),
    CONSTRAINT chk_discharge_after CHECK (discharge_date IS NULL OR discharge_date >= admit_date)
);
-- =========================================================
-- SYMPTOM (reference)
-- =========================================================
CREATE TABLE symptom (
    symptom_id            NUMBER          DEFAULT seq_symptom_id.NEXTVAL PRIMARY KEY,
    symptom_name            VARCHAR2(100)   NOT NULL UNIQUE
);
-- =========================================================
-- DIAGNOSIS
-- =========================================================
CREATE TABLE diagnosis (
    diagnosis_id           NUMBER           DEFAULT seq_diagnosis_id.NEXTVAL PRIMARY KEY,
    patient_id                NUMBER           NOT NULL,
    doctor_id                  NUMBER           NOT NULL,
    appointment_id               NUMBER,
    admission_id                  NUMBER,
    disease_name                     VARCHAR2(150)   NOT NULL,
    disease_code                       VARCHAR2(15),           -- e.g. ICD-10 style
    severity                            VARCHAR2(10)     CHECK (severity IN ('MILD','MODERATE','SEVERE')),
    diagnosis_date                      DATE             DEFAULT SYSDATE NOT NULL,
    CONSTRAINT fk_diag_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_diag_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
    CONSTRAINT fk_diag_appt     FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id),
    CONSTRAINT fk_diag_adm      FOREIGN KEY (admission_id) REFERENCES admission(admission_id),
    CONSTRAINT chk_diag_one_encounter CHECK (
        (appointment_id IS NOT NULL AND admission_id IS NULL) OR
        (appointment_id IS NULL AND admission_id IS NOT NULL)
    )
);
-- =========================================================
-- DIAGNOSIS_SYMPTOM (bridge, M:M)
-- =========================================================
CREATE TABLE diagnosis_symptom (
    diagnosis_id   NUMBER NOT NULL,
    symptom_id     NUMBER NOT NULL,
    CONSTRAINT pk_diag_symptom PRIMARY KEY (diagnosis_id, symptom_id),
    CONSTRAINT fk_ds_diag FOREIGN KEY (diagnosis_id) REFERENCES diagnosis(diagnosis_id) ON DELETE CASCADE,
    CONSTRAINT fk_ds_symptom FOREIGN KEY (symptom_id) REFERENCES symptom(symptom_id)
);
-- =========================================================
-- VITAL_SIGN
-- =========================================================
CREATE TABLE vital_sign (
    vital_id             NUMBER            DEFAULT seq_vital_id.NEXTVAL PRIMARY KEY,
    patient_id             NUMBER            NOT NULL,
    appointment_id            NUMBER,
    admission_id                 NUMBER,
    recorded_at                    TIMESTAMP        DEFAULT SYSTIMESTAMP NOT NULL,
    temperature_c                    NUMBER(4,1)       CHECK (temperature_c BETWEEN 25 AND 45),
    pulse_rate                      NUMBER(3)       CHECK (pulse_rate BETWEEN 20 AND 250),
    systolic_bp                          NUMBER(3)        CHECK (systolic_bp BETWEEN 50 AND 260),
    diastolic_bp                            NUMBER(3)        CHECK (diastolic_bp BETWEEN 30 AND 180),
    spo2_percent                             NUMBER(4,1)      CHECK (spo2_percent BETWEEN 0 AND 100),
    height_cm                                    NUMBER(5,1),
    weight_kg                                      NUMBER(5,1),
    CONSTRAINT fk_vital_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_vital_appt      FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id),
    CONSTRAINT fk_vital_adm       FOREIGN KEY (admission_id) REFERENCES admission(admission_id)
);
-- =========================================================
-- CLINICAL_NOTE
-- =========================================================
CREATE TABLE clinical_note (
    note_id              NUMBER            DEFAULT seq_note_id.NEXTVAL PRIMARY KEY,
    patient_id              NUMBER           NOT NULL,
    doctor_id                 NUMBER           NOT NULL,
    appointment_id               NUMBER,
    admission_id                   NUMBER,
    note_text                        CLOB              NOT NULL,
    created_at                         TIMESTAMP         DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT fk_note_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_note_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
    CONSTRAINT fk_note_appt     FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id),
    CONSTRAINT fk_note_adm      FOREIGN KEY (admission_id) REFERENCES admission(admission_id)
);
-- =========================================================
-- MEDICINE
-- =========================================================
CREATE TABLE medicine (
    medicine_id            NUMBER           DEFAULT seq_medicine_id.NEXTVAL PRIMARY KEY,
    medicine_code             VARCHAR2(20)      NOT NULL UNIQUE,
    medicine_name                 VARCHAR2(120)    NOT NULL,
    category                         VARCHAR2(50),
    unit_price                         NUMBER(8,2)      NOT NULL CHECK (unit_price >= 0),
    stock_quantity                       NUMBER(8)        DEFAULT 0 NOT NULL CHECK (stock_quantity >= 0),
    reorder_level                          NUMBER(8)         DEFAULT 20 NOT NULL,
    expiry_date                              DATE
);
-- =========================================================
-- PRESCRIPTION
-- =========================================================
CREATE TABLE prescription (
    prescription_id         NUMBER            DEFAULT seq_prescription_id.NEXTVAL PRIMARY KEY,
    patient_id                 NUMBER             NOT NULL,
    doctor_id                    NUMBER             NOT NULL,
    appointment_id                    NUMBER,
    prescribed_date                      DATE               DEFAULT SYSDATE NOT NULL,
    status                                  VARCHAR2(15)       DEFAULT 'ACTIVE'
                                               CHECK (status IN ('ACTIVE','FULFILLED','CANCELLED')),
    CONSTRAINT fk_presc_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_presc_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
    CONSTRAINT fk_presc_appt     FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id)
);
-- =========================================================
-- PRESCRIPTION_ITEM
-- =========================================================
CREATE TABLE prescription_item (
    prescription_item_id  NUMBER         DEFAULT seq_presc_item_id.NEXTVAL PRIMARY KEY,
    prescription_id            NUMBER          NOT NULL,
    medicine_id                  NUMBER           NOT NULL,
    dosage                         VARCHAR2(50)     NOT NULL,       -- e.g. '500mg twice daily'
    duration_days                   NUMBER(4)        NOT NULL CHECK (duration_days > 0),
    quantity                            NUMBER(6)        NOT NULL CHECK (quantity > 0),
    CONSTRAINT uq_presc_medicine UNIQUE (prescription_id, medicine_id),
    CONSTRAINT fk_pi_prescription FOREIGN KEY (prescription_id)
        REFERENCES prescription(prescription_id) ON DELETE CASCADE,
    CONSTRAINT fk_pi_medicine     FOREIGN KEY (medicine_id) REFERENCES medicine(medicine_id)
);
-- =========================================================
-- LAB_TEST_CATALOG
-- =========================================================
CREATE TABLE lab_test_catalog (
    lab_test_id            NUMBER            DEFAULT seq_labtest_id.NEXTVAL PRIMARY KEY,
    test_code                   VARCHAR2(20)     NOT NULL UNIQUE,
    test_name                      VARCHAR2(100)    NOT NULL,
    normal_range                      VARCHAR2(50),
    price                                 NUMBER(8,2)      NOT NULL CHECK (price >= 0)
);
-- =========================================================
-- LAB_ORDER
-- =========================================================
CREATE TABLE lab_order (
    lab_order_id           NUMBER           DEFAULT seq_laborder_id.NEXTVAL PRIMARY KEY,
    patient_id                 NUMBER            NOT NULL,
    doctor_id                     NUMBER            NOT NULL,
    lab_test_id                     NUMBER            NOT NULL,
    order_date                         DATE              DEFAULT SYSDATE NOT NULL,
    status                                 VARCHAR2(20)     DEFAULT 'ORDERED' NOT NULL
                                        CHECK (status IN ('ORDERED','SAMPLE_COLLECTED','RESULT_READY','CANCELLED')),
    result_value                             VARCHAR2(200),
    result_date                                 DATE,
    CONSTRAINT fk_lo_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_lo_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
    CONSTRAINT fk_lo_test    FOREIGN KEY (lab_test_id) REFERENCES lab_test_catalog(lab_test_id),
    CONSTRAINT chk_result_after_order CHECK (result_date IS NULL OR result_date >= order_date)
);
-- =========================================================
-- INSURANCE_POLICY
-- =========================================================
CREATE TABLE insurance_policy (
    policy_id               NUMBER           DEFAULT seq_policy_id.NEXTVAL PRIMARY KEY,
    patient_id                 NUMBER           NOT NULL UNIQUE,       -- enforces 1:0..1
    policy_no                      VARCHAR2(30)     NOT NULL UNIQUE,
    provider_name                     VARCHAR2(100)    NOT NULL,
    coverage_amount                      NUMBER(10,2)     NOT NULL CHECK (coverage_amount >= 0),
    valid_until                             DATE             NOT NULL,
    CONSTRAINT fk_policy_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id)
);
-- =========================================================
-- BILL
-- =========================================================
CREATE TABLE bill (
    bill_id                  NUMBER           DEFAULT seq_bill_id.NEXTVAL PRIMARY KEY,
    patient_id                  NUMBER           NOT NULL,
    appointment_id                  NUMBER,
    admission_id                       NUMBER,
    bill_date                             DATE              DEFAULT SYSDATE NOT NULL,
    status                                     VARCHAR2(15)     DEFAULT 'UNPAID' NOT NULL
                                            CHECK (status IN ('UNPAID','PARTIALLY_PAID','PAID','CANCELLED')),
    CONSTRAINT fk_bill_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
      CONSTRAINT fk_bill_appt     FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id),
      CONSTRAINT fk_bill_adm      FOREIGN KEY (admission_id) REFERENCES admission(admission_id)
);
-- =========================================================
-- BILL_ITEM
-- =========================================================
CREATE TABLE bill_item (
    bill_item_id              NUMBER          DEFAULT seq_bill_item_id.NEXTVAL PRIMARY KEY,
    bill_id                      NUMBER          NOT NULL,
    item_description                 VARCHAR2(150)    NOT NULL,
    item_category                        VARCHAR2(30)     CHECK (item_category IN
 ('CONSULTATION','MEDICINE','LAB_TEST','ROOM_CHARGE','PROCEDURE','OTHER')),
     amount                                NUMBER(10,2)    NOT NULL CHECK (amount >= 0),
     CONSTRAINT fk_bi_bill FOREIGN KEY (bill_id) REFERENCES bill(bill_id) ON DELETE CASCADE
);
-- =========================================================
-- PAYMENT
-- =========================================================
CREATE TABLE payment (
    payment_id               NUMBER           DEFAULT seq_payment_id.NEXTVAL PRIMARY KEY,
    bill_id                      NUMBER            NOT NULL,
    amount_paid                     NUMBER(10,2)      NOT NULL CHECK (amount_paid > 0),
    payment_mode                        VARCHAR2(15)     NOT NULL
                                         CHECK (payment_mode IN ('CASH','CARD','UPI',  'INSURANCE','NET_BANKING')),
    paid_date                               DATE             DEFAULT SYSDATE NOT NULL,
    CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id) REFERENCES bill(bill_id)
);
-- =========================================================
-- SERVICE_QUEUE
-- =========================================================
CREATE TABLE service_queue (
    queue_id                 NUMBER           DEFAULT seq_queue_id.NEXTVAL PRIMARY KEY,
    queue_type                   VARCHAR2(10)     NOT NULL CHECK (queue_type IN ('OPD','EMERGENCY','LAB','PHARMACY')),
    queue_number                     NUMBER(5)         NOT NULL,
    queue_date                          DATE              DEFAULT TRUNC(SYSDATE) NOT NULL,
    patient_id                             NUMBER            NOT NULL,
    doctor_id                                  NUMBER,
    department_id                                 NUMBER,
    priority_level                                   NUMBER(1)         DEFAULT 3 NOT NULL CHECK (priority_level BETWEEN 1 AND 5),
                                                      -- 1 = most urgent (emergency), 5 = routine
    arrival_time                                     TIMESTAMP        DEFAULT SYSTIMESTAMP NOT NULL,
     called_time                                         TIMESTAMP,
     status                                                 VARCHAR2(12)     DEFAULT 'WAITING' NOT NULL
                                                           CHECK (status IN ('WAITING',  
                                                                 'CALLED','IN_SERVICE','COMPLETED',  'CANCELLED')),
     CONSTRAINT uq_queue_slot UNIQUE (queue_type, queue_date, queue_number),
     CONSTRAINT fk_queue_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
     CONSTRAINT fk_queue_doctor FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
     CONSTRAINT fk_queue_dept    FOREIGN KEY (department_id) REFERENCES department(department_id)
);
-- =========================================================
-- APP_USER (application-level identity mapped to a DB role)
-- =========================================================
CREATE TABLE app_user (
    user_id                  NUMBER           DEFAULT seq_user_id.NEXTVAL PRIMARY KEY,
    username                     VARCHAR2(50)     NOT NULL UNIQUE,
    role_name                       VARCHAR2(20)     NOT NULL CHECK (role_name IN
 ('ADMIN','DOCTOR','NURSE','RECEPTIONIST','LAB','PHARMACY','BILLING','PATIENT')),
     linked_doctor_id                    NUMBER,
     linked_nurse_id                        NUMBER,
     linked_patient_id                        NUMBER,
     is_active                                CHAR(1)         DEFAULT 'Y' NOT NULL CHECK (is_active IN ('Y','N')),
     created_at                                 DATE           DEFAULT SYSDATE NOT NULL,
     CONSTRAINT fk_user_doctor FOREIGN KEY (linked_doctor_id) REFERENCES doctor(doctor_id),
     CONSTRAINT fk_user_nurse   FOREIGN KEY (linked_nurse_id)   REFERENCES nurse(nurse_id),
     CONSTRAINT fk_user_patient FOREIGN KEY (linked_patient_id) REFERENCES patient(patient_id),
     CONSTRAINT chk_user_link CHECK (
         (CASE WHEN linked_doctor_id IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN linked_nurse_id   IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN linked_patient_id IS NOT NULL THEN 1 ELSE 0 END) <= 1
     )
);
-- =========================================================
-- AUDIT_LOG
-- =========================================================
CREATE TABLE audit_log (
    audit_id                 NUMBER            DEFAULT seq_audit_id.NEXTVAL PRIMARY KEY,
    user_id                     NUMBER,
    table_name                      VARCHAR2(30)     NOT NULL,
    record_id                          NUMBER,
    operation                             VARCHAR2(10)     NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    old_value                                CLOB,
    new_value                                    CLOB,
    action_timestamp                                TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES app_user(user_id)
);
-- =========================================================
-- ML_PREDICTION
-- =========================================================
CREATE TABLE ml_prediction (
    prediction_id              NUMBER           DEFAULT seq_prediction_id.NEXTVAL PRIMARY KEY,
    patient_id                    NUMBER           NOT NULL,
    appointment_id                    NUMBER           NOT NULL,
    model_name                           VARCHAR2(50)      NOT NULL,
    model_version                            VARCHAR2(10)     NOT NULL,
    prediction                                 VARCHAR2(15)     NOT NULL CHECK (prediction IN ('NO_SHOW','ATTENDED')),
    probability                                    NUMBER(5,4)       NOT NULL CHECK (probability BETWEEN 0 AND 1),
    prediction_date                                   DATE              DEFAULT SYSDATE NOT NULL,
    CONSTRAINT uq_ml_appt UNIQUE (appointment_id, model_name, model_version),
    CONSTRAINT fk_ml_patient FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
    CONSTRAINT fk_ml_appt     FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id)
);
