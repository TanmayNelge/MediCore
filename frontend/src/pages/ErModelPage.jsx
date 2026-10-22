import mermaid from "mermaid";
import { useEffect, useRef, useState, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import {
  GitBranch, ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2,
  Download, Layers, Database, Table, HelpCircle, CheckCircle2,
  ChevronRight, Search, Info, Eye, Sparkles, ArrowRight, ShieldCheck
} from "lucide-react";

// =====================================================================
// MERMAID ER DEFINITIONS (Accurate Oracle XE 28-Table Relational Schema)
// =====================================================================

const ER_DIAGRAMS = {
  MASTER: `erDiagram
    DEPARTMENT ||--o{ DOCTOR : "employs"
    DEPARTMENT ||--o{ NURSE : "employs"
    DEPARTMENT ||--o{ ROOM_BED : "contains"
    DEPARTMENT ||--o{ SERVICE_QUEUE : "routed to"
    DOCTOR ||--o{ STAFF_SCHEDULE : "scheduled"
    DOCTOR ||--o{ APPOINTMENT : "conducts"
    DOCTOR ||--o{ ADMISSION : "admits"
    DOCTOR ||--o{ DIAGNOSIS : "diagnoses"
    DOCTOR ||--o{ CLINICAL_NOTE : "writes"
    DOCTOR ||--o{ PRESCRIPTION : "issues"
    DOCTOR ||--o{ LAB_ORDER : "orders"
    DOCTOR ||--o{ SERVICE_QUEUE : "consults"
    PATIENT ||--o{ APPOINTMENT : "books"
    PATIENT ||--o{ ADMISSION : "admitted as"
    PATIENT ||--o{ DIAGNOSIS : "receives"
    PATIENT ||--o{ VITAL_SIGN : "recorded for"
    PATIENT ||--o{ CLINICAL_NOTE : "has notes"
    PATIENT ||--o{ PRESCRIPTION : "prescribed to"
    PATIENT ||--o{ LAB_ORDER : "tested for"
    PATIENT ||--o| INSURANCE_POLICY : "holds policy"
    PATIENT ||--o{ BILL : "billed to"
    PATIENT ||--o{ SERVICE_QUEUE : "waits in"
    DISEASE ||--o{ DIAGNOSIS : "classifies"
    ML_MODEL_RUN ||--o{ ML_PREDICTION : "produces"
    ROOM_BED ||--o{ ADMISSION : "assigned to"
    APPOINTMENT ||--o{ ML_PREDICTION : "risk scored"
    APPOINTMENT ||--o{ DIAGNOSIS : "diagnosed in"
    APPOINTMENT ||--o{ BILL : "billed for"
    ADMISSION ||--o{ DIAGNOSIS : "diagnosed in"
    ADMISSION ||--o{ BILL : "billed for"
    DIAGNOSIS ||--o{ DIAGNOSIS_SYMPTOM : "associates"
    SYMPTOM ||--o{ DIAGNOSIS_SYMPTOM : "exhibits"
    PRESCRIPTION ||--o{ PRESCRIPTION_ITEM : "contains"
    MEDICINE ||--o{ PRESCRIPTION_ITEM : "dispensed"
    LAB_TEST_CATALOG ||--o{ LAB_ORDER : "defines"
    BILL ||--o{ BILL_ITEM : "itemizes"
    BILL ||--o{ PAYMENT : "settled by"
    APP_USER ||--o{ AUDIT_LOG : "audited in"

    DEPARTMENT {
        number department_id PK
        varchar2 department_name
        number head_doctor_id FK
        varchar2 location
    }
    DOCTOR {
        number doctor_id PK
        number department_id FK
        varchar2 first_name
        varchar2 last_name
        varchar2 specialization
        varchar2 license_no
        number consultation_fee
    }
    NURSE {
        number nurse_id PK
        number department_id FK
        varchar2 first_name
        varchar2 last_name
        varchar2 shift
        varchar2 license_no
    }
    ROOM_BED {
        number room_bed_id PK
        number department_id FK
        varchar2 room_no
        varchar2 bed_no
        number daily_charge
        varchar2 status
    }
    PATIENT {
        number patient_id PK
        varchar2 first_name
        varchar2 last_name
        date dob
        varchar2 gender
        varchar2 blood_group
        varchar2 phone
        varchar2 email
        varchar2 city
    }
    APPOINTMENT {
        number appointment_id PK
        number patient_id FK
        number doctor_id FK
        date appt_date
        varchar2 appt_time
        varchar2 appt_type
        varchar2 status
    }
    ADMISSION {
        number admission_id PK
        number patient_id FK
        number room_bed_id FK
        number admitting_doctor_id FK
        date admit_date
        date discharge_date
        varchar2 status
    }
    DIAGNOSIS {
        number diagnosis_id PK
        number patient_id FK
        number doctor_id FK
        number appointment_id FK
        varchar2 disease_code FK
        varchar2 severity
    }
    PRESCRIPTION {
        number prescription_id PK
        number patient_id FK
        number doctor_id FK
        number appointment_id FK
        date prescribed_date
        varchar2 status
    }
    MEDICINE {
        number medicine_id PK
        varchar2 medicine_code
        varchar2 medicine_name
        varchar2 category
        number unit_price
        number stock_quantity
        number reorder_level
    }
    LAB_ORDER {
        number lab_order_id PK
        number patient_id FK
        number doctor_id FK
        number lab_test_id FK
        date order_date
        varchar2 status
        varchar2 result_value
    }
    BILL {
        number bill_id PK
        number patient_id FK
        number appointment_id FK
        number admission_id FK
        date bill_date
        number total_amount
        varchar2 status
    }
    PAYMENT {
        number payment_id PK
        number bill_id FK
        number amount_paid
        varchar2 payment_mode
        date paid_date
    }
    SERVICE_QUEUE {
        number queue_id PK
        number patient_id FK
        number doctor_id FK
        varchar2 queue_type
        number priority_level
        varchar2 status
    }
    ML_PREDICTION {
        number prediction_id PK
        number appointment_id FK
        number run_id FK
        varchar2 prediction
        number probability
        varchar2 risk_factors
    }
    ML_MODEL_RUN {
        number run_id PK
        varchar2 model_name
        varchar2 model_version
        number roc_auc
        number threshold
        char is_active
        clob metrics_json
    }
    DISEASE {
        varchar2 disease_code PK
        varchar2 disease_name
        char is_chronic
    }`,

  CLINICAL: `erDiagram
    PATIENT ||--o{ APPOINTMENT : "schedules"
    DOCTOR ||--o{ APPOINTMENT : "conducts"
    APPOINTMENT ||--o{ DIAGNOSIS : "recorded during"
    PATIENT ||--o{ DIAGNOSIS : "diagnosed with"
    DOCTOR ||--o{ DIAGNOSIS : "makes diagnosis"
    DIAGNOSIS ||--o{ DIAGNOSIS_SYMPTOM : "links"
    SYMPTOM ||--o{ DIAGNOSIS_SYMPTOM : "observed"
    PATIENT ||--o{ VITAL_SIGN : "monitored"
    APPOINTMENT ||--o{ VITAL_SIGN : "measured at"
    PATIENT ||--o{ CLINICAL_NOTE : "has"
    DOCTOR ||--o{ CLINICAL_NOTE : "authors"
    DISEASE ||--o{ DIAGNOSIS : "classifies"
    APPOINTMENT ||--o{ ML_PREDICTION : "risk scored"

    PATIENT {
        number patient_id PK
        varchar2 first_name
        varchar2 last_name
        date dob
        varchar2 gender
        varchar2 blood_group
        varchar2 phone
    }
    DOCTOR {
        number doctor_id PK
        varchar2 first_name
        varchar2 last_name
        varchar2 specialization
        varchar2 license_no
        number consultation_fee
    }
    APPOINTMENT {
        number appointment_id PK
        number patient_id FK
        number doctor_id FK
        date appt_date
        varchar2 appt_time
        varchar2 status
    }
    DIAGNOSIS {
        number diagnosis_id PK
        number patient_id FK
        number doctor_id FK
        number appointment_id FK
        varchar2 disease_code FK
        varchar2 severity
    }
    SYMPTOM {
        number symptom_id PK
        varchar2 symptom_name
    }
    DIAGNOSIS_SYMPTOM {
        number diagnosis_id PK_FK
        number symptom_id PK_FK
    }
    VITAL_SIGN {
        number vital_id PK
        number patient_id FK
        timestamp recorded_at
        number temperature_c
        number pulse_rate
        number systolic_bp
        number diastolic_bp
        number spo2_percent
    }
    CLINICAL_NOTE {
        number note_id PK
        number patient_id FK
        number doctor_id FK
        date created_at
        varchar2 note_text
    }
    DISEASE {
        varchar2 disease_code PK
        varchar2 disease_name
        char is_chronic
    }
    ML_PREDICTION {
        number prediction_id PK
        number appointment_id FK
        number run_id FK
        varchar2 prediction
        number probability
    }`,

  ADMISSION: `erDiagram
    DEPARTMENT ||--o{ DOCTOR : "employs"
    DEPARTMENT ||--o{ NURSE : "employs"
    DEPARTMENT ||--o{ ROOM_BED : "manages"
    PATIENT ||--o{ ADMISSION : "undergoes"
    ROOM_BED ||--o{ ADMISSION : "accommodates"
    DOCTOR ||--o{ ADMISSION : "attending physician"
    DOCTOR ||--o{ STAFF_SCHEDULE : "scheduled"

    DEPARTMENT {
        number department_id PK
        varchar2 department_name
        number head_doctor_id FK
        varchar2 location
    }
    DOCTOR {
        number doctor_id PK
        number department_id FK
        varchar2 first_name
        varchar2 last_name
        varchar2 specialization
    }
    NURSE {
        number nurse_id PK
        number department_id FK
        varchar2 first_name
        varchar2 last_name
        varchar2 shift
    }
    ROOM_BED {
        number room_bed_id PK
        number department_id FK
        varchar2 room_no
        varchar2 bed_no
        number daily_charge
        varchar2 status
    }
    ADMISSION {
        number admission_id PK
        number patient_id FK
        number room_bed_id FK
        number admitting_doctor_id FK
        date admit_date
        date discharge_date
        varchar2 status
    }
    PATIENT {
        number patient_id PK
        varchar2 first_name
        varchar2 last_name
        varchar2 phone
        varchar2 emergency_contact_name
    }
    STAFF_SCHEDULE {
        number schedule_id PK
        number doctor_id FK
        date schedule_date
        varchar2 start_time
        varchar2 end_time
    }`,

  PHARMACY_LAB: `erDiagram
    PATIENT ||--o{ PRESCRIPTION : "receives"
    DOCTOR ||--o{ PRESCRIPTION : "prescribes"
    PRESCRIPTION ||--o{ PRESCRIPTION_ITEM : "contains"
    MEDICINE ||--o{ PRESCRIPTION_ITEM : "itemized in"
    PATIENT ||--o{ LAB_ORDER : "specimen from"
    DOCTOR ||--o{ LAB_ORDER : "requested by"
    LAB_TEST_CATALOG ||--o{ LAB_ORDER : "specifies"

    PATIENT {
        number patient_id PK
        varchar2 first_name
        varchar2 last_name
        date dob
        varchar2 phone
    }
    DOCTOR {
        number doctor_id PK
        varchar2 first_name
        varchar2 last_name
        varchar2 specialization
    }
    PRESCRIPTION {
        number prescription_id PK
        number patient_id FK
        number doctor_id FK
        number appointment_id FK
        date prescribed_date
        varchar2 status
    }
    PRESCRIPTION_ITEM {
        number prescription_item_id PK
        number prescription_id FK
        number medicine_id FK
        varchar2 dosage
        number duration_days
        number quantity
    }
    MEDICINE {
        number medicine_id PK
        varchar2 medicine_code
        varchar2 medicine_name
        varchar2 category
        number unit_price
        number stock_quantity
        number reorder_level
    }
    LAB_TEST_CATALOG {
        number lab_test_id PK
        varchar2 test_code
        varchar2 test_name
        varchar2 normal_range
        number price
    }
    LAB_ORDER {
        number lab_order_id PK
        number patient_id FK
        number doctor_id FK
        number lab_test_id FK
        date order_date
        varchar2 status
        varchar2 result_value
    }`,

  FINANCIAL: `erDiagram
    PATIENT ||--o{ BILL : "billed"
    PATIENT ||--o| INSURANCE_POLICY : "covered by"
    BILL ||--o{ BILL_ITEM : "line items"
    BILL ||--o{ PAYMENT : "paid with"
    PATIENT ||--o{ SERVICE_QUEUE : "enqueued"
    DEPARTMENT ||--o{ SERVICE_QUEUE : "service point"
    DOCTOR ||--o{ SERVICE_QUEUE : "assigned doc"

    PATIENT {
        number patient_id PK
        varchar2 first_name
        varchar2 last_name
        varchar2 phone
        varchar2 email
    }
    INSURANCE_POLICY {
        number policy_id PK
        number patient_id FK
        varchar2 policy_no
        varchar2 provider_name
        number coverage_amount
        date valid_until
    }
    BILL {
        number bill_id PK
        number patient_id FK
        number appointment_id FK
        number admission_id FK
        date bill_date
        varchar2 status
    }
    BILL_ITEM {
        number bill_item_id PK
        number bill_id FK
        varchar2 item_description
        varchar2 item_category
        number amount
    }
    PAYMENT {
        number payment_id PK
        number bill_id FK
        number amount_paid
        varchar2 payment_mode
        date paid_date
    }
    SERVICE_QUEUE {
        number queue_id PK
        number patient_id FK
        number doctor_id FK
        number department_id FK
        varchar2 queue_type
        number priority_level
        varchar2 status
    }`
};

// =====================================================================
// DETAILED CROW'S FOOT NOTATION GUIDE (Industry Standard IE Specification)
// =====================================================================

const CROWS_FOOT_SYMBOLS = [
  {
    code: "||--||",
    name: "One and Only One",
    altName: "Mandatory One",
    cardinality: "1 to 1",
    min: 1,
    max: 1,
    symbolText: "||",
    description: "Exactly one related record is strictly required. Neither zero nor more than one is permitted.",
    example: "Each Appointment corresponds to exactly one Patient encounter slot.",
    svgPath: (
      <svg width="44" height="24" viewBox="0 0 44 24" className="shrink-0">
        <line x1="2" y1="12" x2="42" y2="12" stroke="#0f766e" strokeWidth="2" />
        <line x1="28" y1="4" x2="28" y2="20" stroke="#0f766e" strokeWidth="2.5" />
        <line x1="36" y1="4" x2="36" y2="20" stroke="#0f766e" strokeWidth="2.5" />
      </svg>
    )
  },
  {
    code: "||--o|",
    name: "Zero or One",
    altName: "Optional One",
    cardinality: "0 to 1",
    min: 0,
    max: 1,
    symbolText: "o|",
    description: "At most one related record may exist. It is optional (minimum 0, maximum 1).",
    example: "Each Patient holds zero or one Insurance Policy (not all patients have insurance).",
    svgPath: (
      <svg width="44" height="24" viewBox="0 0 44 24" className="shrink-0">
        <line x1="2" y1="12" x2="42" y2="12" stroke="#0f766e" strokeWidth="2" />
        <circle cx="26" cy="12" r="5" fill="#ffffff" stroke="#0f766e" strokeWidth="2" />
        <line x1="36" y1="4" x2="36" y2="20" stroke="#0f766e" strokeWidth="2.5" />
      </svg>
    )
  },
  {
    code: "||--o{",
    name: "Zero or Many",
    altName: "Optional Many (Crow's Foot + Circle)",
    cardinality: "0 to N",
    min: 0,
    max: "N",
    symbolText: "o{",
    description: "Any number of related records can exist (0, 1, or many). The circle indicates optionality, while the 3-pronged fork represents many.",
    example: "One Doctor can conduct zero or many Appointments. One Patient can have zero or many Prescriptions.",
    svgPath: (
      <svg width="44" height="24" viewBox="0 0 44 24" className="shrink-0">
        <line x1="2" y1="12" x2="26" y2="12" stroke="#0f766e" strokeWidth="2" />
        <circle cx="20" cy="12" r="5" fill="#ffffff" stroke="#0f766e" strokeWidth="2" />
        <path d="M42 4 L28 12 L42 20 M28 12 L42 12" fill="none" stroke="#0f766e" strokeWidth="2" />
      </svg>
    )
  },
  {
    code: "||--|{",
    name: "One or Many",
    altName: "Mandatory Many (Crow's Foot + Bar)",
    cardinality: "1 to N",
    min: 1,
    max: "N",
    symbolText: "|{",
    description: "At least one related record is strictly required, up to many. Must not be empty.",
    example: "Every Bill must contain one or more Bill Items (an empty invoice is invalid).",
    svgPath: (
      <svg width="44" height="24" viewBox="0 0 44 24" className="shrink-0">
        <line x1="2" y1="12" x2="28" y2="12" stroke="#0f766e" strokeWidth="2" />
        <line x1="20" y1="4" x2="20" y2="20" stroke="#0f766e" strokeWidth="2.5" />
        <path d="M42 4 L28 12 L42 20 M28 12 L42 12" fill="none" stroke="#0f766e" strokeWidth="2" />
      </svg>
    )
  }
];

// Complete 28-Table Relational Schema Catalog with relationships
const TABLE_METADATA = [
  {
    name: "PATIENT",
    domain: "Clinical",
    pks: ["patient_id"],
    fks: [],
    desc: "Master patient directory storing demographic attributes and contact information.",
    relations: [
      { target: "APPOINTMENT", type: "||--o{", label: "books", meaning: "One patient can book 0..N appointments" },
      { target: "ADMISSION", type: "||--o{", label: "admitted as", meaning: "One patient can have 0..N hospital admissions" },
      { target: "DIAGNOSIS", type: "||--o{", label: "receives", meaning: "One patient can receive 0..N clinical diagnoses" },
      { target: "VITAL_SIGN", type: "||--o{", label: "recorded for", meaning: "One patient has 0..N recorded vital signs" },
      { target: "PRESCRIPTION", type: "||--o{", label: "prescribed to", meaning: "One patient receives 0..N prescriptions" },
      { target: "BILL", type: "||--o{", label: "billed to", meaning: "One patient owes 0..N medical bills" },
      { target: "INSURANCE_POLICY", type: "||--o|", label: "holds policy", meaning: "One patient holds 0..1 insurance policy" }
    ]
  },
  {
    name: "DOCTOR",
    domain: "Staff",
    pks: ["doctor_id"],
    fks: ["department_id"],
    desc: "Licensed physicians with clinical specialization, license registry, and consultation fee.",
    relations: [
      { target: "DEPARTMENT", type: "}o--||", label: "employed by", meaning: "Every doctor belongs to exactly 1 department" },
      { target: "APPOINTMENT", type: "||--o{", label: "conducts", meaning: "One doctor conducts 0..N scheduled consultations" },
      { target: "DIAGNOSIS", type: "||--o{", label: "diagnoses", meaning: "One doctor authors 0..N patient diagnoses" },
      { target: "PRESCRIPTION", type: "||--o{", label: "issues", meaning: "One doctor issues 0..N prescription orders" },
      { target: "LAB_ORDER", type: "||--o{", label: "orders", meaning: "One doctor orders 0..N diagnostic lab tests" }
    ]
  },
  {
    name: "DEPARTMENT",
    domain: "Admin",
    pks: ["department_id"],
    fks: ["head_doctor_id"],
    desc: "Hospital specialized clinical departments (General Medicine, Cardiology, Orthopedics, etc.).",
    relations: [
      { target: "DOCTOR", type: "||--o{", label: "employs", meaning: "One department employs 0..N physicians" },
      { target: "NURSE", type: "||--o{", label: "employs", meaning: "One department employs 0..N nursing staff" },
      { target: "ROOM_BED", type: "||--o{", label: "contains", meaning: "One department contains 0..N inpatient room beds" }
    ]
  },
  {
    name: "NURSE",
    domain: "Staff",
    pks: ["nurse_id"],
    fks: ["department_id"],
    desc: "Registered hospital nurses assigned to departments, triage consoles, and rotating shifts.",
    relations: [
      { target: "DEPARTMENT", type: "}o--||", label: "assigned to", meaning: "Every nurse belongs to exactly 1 department" }
    ]
  },
  {
    name: "STAFF_SCHEDULE",
    domain: "Admin",
    pks: ["schedule_id"],
    fks: ["doctor_id"],
    desc: "Duty rosters, working hours, and maximum patient capacity for clinical staff.",
    relations: [
      { target: "DOCTOR", type: "}o--||", label: "scheduled for", meaning: "Every schedule slot belongs to 1 doctor" }
    ]
  },
  {
    name: "ROOM_BED",
    domain: "Facilities",
    pks: ["room_bed_id"],
    fks: ["department_id"],
    desc: "Inpatient room and bed registry, daily tariffs, and occupancy state (AVAILABLE vs OCCUPIED).",
    relations: [
      { target: "DEPARTMENT", type: "}o--||", label: "located in", meaning: "Every bed belongs to 1 hospital department" },
      { target: "ADMISSION", type: "||--o{", label: "assigned to", meaning: "One bed accommodates 0..N patient admission stays" }
    ]
  },
  {
    name: "APPOINTMENT",
    domain: "Clinical",
    pks: ["appointment_id"],
    fks: ["patient_id", "doctor_id"],
    desc: "Outpatient consultation bookings with date, timeslot, arrival state, and cancellation tracking.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "booked by", meaning: "Every appointment belongs to exactly 1 patient" },
      { target: "DOCTOR", type: "}o--||", label: "assigned doctor", meaning: "Every appointment is assigned to exactly 1 doctor" },
      { target: "DIAGNOSIS", type: "||--o{", label: "diagnosed in", meaning: "One appointment encounter can yield 0..N diagnoses" },
      { target: "ML_PREDICTION", type: "||--o|", label: "risk scored", meaning: "One appointment has 0..1 ML no-show risk score" }
    ]
  },
  {
    name: "ADMISSION",
    domain: "Inpatient",
    pks: ["admission_id"],
    fks: ["patient_id", "room_bed_id", "admitting_doctor_id"],
    desc: "Inpatient hospital stay episodes, attending doctor, bed allocation, and discharge dates.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "patient admitted", meaning: "Every admission corresponds to 1 patient" },
      { target: "ROOM_BED", type: "}o--||", label: "bed assigned", meaning: "Every admission is assigned to 1 room bed" },
      { target: "DOCTOR", type: "}o--||", label: "attending doctor", meaning: "Every admission has 1 admitting doctor" }
    ]
  },
  {
    name: "DIAGNOSIS",
    domain: "Clinical",
    pks: ["diagnosis_id"],
    fks: ["patient_id", "doctor_id", "appointment_id", "admission_id"],
    desc: "Standardized clinical diagnosis with ICD disease code, severity level, and encounter links.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "diagnosed patient", meaning: "Every diagnosis belongs to 1 patient" },
      { target: "DOCTOR", type: "}o--||", label: "diagnosing doctor", meaning: "Every diagnosis is authored by 1 doctor" },
      { target: "DIAGNOSIS_SYMPTOM", type: "||--o{", label: "manifests", meaning: "One diagnosis links to 0..N presenting symptoms" }
    ]
  },
  {
    name: "SYMPTOM",
    domain: "Clinical",
    pks: ["symptom_id"],
    fks: [],
    desc: "Medical symptom taxonomy (Fever, Chest Pain, Dyspnea) evaluated during triage.",
    relations: [
      { target: "DIAGNOSIS_SYMPTOM", type: "||--o{", label: "associated with", meaning: "One symptom can appear in 0..N diagnoses" }
    ]
  },
  {
    name: "DIAGNOSIS_SYMPTOM",
    domain: "Clinical",
    pks: ["diagnosis_id", "symptom_id"],
    fks: ["diagnosis_id", "symptom_id"],
    desc: "Composite bridge table modeling the M:N relationship between diagnoses and symptoms.",
    relations: [
      { target: "DIAGNOSIS", type: "}o--||", label: "parent diagnosis", meaning: "Links to the diagnosis record" },
      { target: "SYMPTOM", type: "}o--||", label: "referenced symptom", meaning: "Links to the symptom taxonomy" }
    ]
  },
  {
    name: "VITAL_SIGN",
    domain: "Clinical",
    pks: ["vital_id"],
    fks: ["patient_id", "appointment_id", "admission_id"],
    desc: "Timestamped vital measurements (Temperature, Pulse, Blood Pressure, SpO2, BMI).",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "patient vitals", meaning: "Every vital measurement belongs to 1 patient" }
    ]
  },
  {
    name: "CLINICAL_NOTE",
    domain: "Clinical",
    pks: ["note_id"],
    fks: ["patient_id", "doctor_id", "appointment_id", "admission_id"],
    desc: "Physician clinical observations, progress reports, and treatment plans.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "patient file", meaning: "Recorded into 1 patient medical record" },
      { target: "DOCTOR", type: "}o--||", label: "authoring doctor", meaning: "Penned by 1 authorized physician" }
    ]
  },
  {
    name: "MEDICINE",
    domain: "Pharmacy",
    pks: ["medicine_id"],
    fks: [],
    desc: "Pharmaceutical drug inventory, dosage categories, unit price, stock count, and reorder levels.",
    relations: [
      { target: "PRESCRIPTION_ITEM", type: "||--o{", label: "prescribed as", meaning: "One medicine can be itemized in 0..N prescriptions" }
    ]
  },
  {
    name: "PRESCRIPTION",
    domain: "Pharmacy",
    pks: ["prescription_id"],
    fks: ["patient_id", "doctor_id", "appointment_id"],
    desc: "Doctor-issued prescription orders tracking fulfillment status (ACTIVE, FULFILLED).",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "prescribed to", meaning: "Issued to exactly 1 patient" },
      { target: "DOCTOR", type: "}o--||", label: "prescribed by", meaning: "Issued by exactly 1 doctor" },
      { target: "PRESCRIPTION_ITEM", type: "||--|{", label: "contains", meaning: "Contains 1..N medication line items" }
    ]
  },
  {
    name: "PRESCRIPTION_ITEM",
    domain: "Pharmacy",
    pks: ["prescription_item_id"],
    fks: ["prescription_id", "medicine_id"],
    desc: "Itemized medication line items specifying dosage, duration days, and quantities.",
    relations: [
      { target: "PRESCRIPTION", type: "}o--||", label: "part of", meaning: "Belongs to exactly 1 master prescription" },
      { target: "MEDICINE", type: "}o--||", label: "dispenses", meaning: "References exactly 1 cataloged medicine" }
    ]
  },
  {
    name: "LAB_TEST_CATALOG",
    domain: "Diagnostics",
    pks: ["lab_test_id"],
    fks: [],
    desc: "Diagnostic laboratory catalog of available tests, normal reference ranges, and test fees.",
    relations: [
      { target: "LAB_ORDER", type: "||--o{", label: "ordered as", meaning: "One lab test can be ordered 0..N times" }
    ]
  },
  {
    name: "LAB_ORDER",
    domain: "Diagnostics",
    pks: ["lab_order_id"],
    fks: ["patient_id", "doctor_id", "lab_test_id"],
    desc: "Specimen collection tracking, laboratory order status, and validated clinical results.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "patient specimen", meaning: "Specimen taken from 1 patient" },
      { target: "DOCTOR", type: "}o--||", label: "ordering doctor", meaning: "Ordered by 1 physician" },
      { target: "LAB_TEST_CATALOG", type: "}o--||", label: "test type", meaning: "Corresponds to 1 cataloged lab test" }
    ]
  },
  {
    name: "INSURANCE_POLICY",
    domain: "Billing",
    pks: ["policy_id"],
    fks: ["patient_id"],
    desc: "Third-party medical insurance policies, policy numbers, coverage amounts, and validity dates.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "policy holder", meaning: "Belongs to 1 patient (enforces 1:0..1)" }
    ]
  },
  {
    name: "BILL",
    domain: "Billing",
    pks: ["bill_id"],
    fks: ["patient_id", "appointment_id", "admission_id"],
    desc: "Patient consolidated invoice with status (UNPAID, PARTIALLY_PAID, PAID, CANCELLED).",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "billed patient", meaning: "Billed to exactly 1 patient" },
      { target: "BILL_ITEM", type: "||--|{", label: "itemizes", meaning: "Itemized into 1..N billing items" },
      { target: "PAYMENT", type: "||--o{", label: "settled by", meaning: "Settled via 0..N payment transactions" }
    ]
  },
  {
    name: "BILL_ITEM",
    domain: "Billing",
    pks: ["bill_item_id"],
    fks: ["bill_id"],
    desc: "Line items (Consultation, Medicine, Lab Test, Room Charge) with individual charge amounts.",
    relations: [
      { target: "BILL", type: "}o--||", label: "billed in", meaning: "Belongs to exactly 1 parent bill invoice" }
    ]
  },
  {
    name: "PAYMENT",
    domain: "Billing",
    pks: ["payment_id"],
    fks: ["bill_id"],
    desc: "Payment transactions (CASH, CARD, UPI, INSURANCE) with automatic trigger status flips.",
    relations: [
      { target: "BILL", type: "}o--||", label: "pays bill", meaning: "Applied towards exactly 1 bill" }
    ]
  },
  {
    name: "SERVICE_QUEUE",
    domain: "Operations",
    pks: ["queue_id"],
    fks: ["patient_id", "doctor_id", "department_id"],
    desc: "Real-time triage queue managing FIFO and emergency prioritization for patient flow.",
    relations: [
      { target: "PATIENT", type: "}o--||", label: "queued patient", meaning: "Holds 1 waiting patient" },
      { target: "DOCTOR", type: "}o--o|", label: "attending doctor", meaning: "Optionally routed to 1 doctor" }
    ]
  },
  {
    name: "APP_USER",
    domain: "Security",
    pks: ["user_id"],
    fks: ["linked_doctor_id", "linked_nurse_id", "linked_patient_id"],
    desc: "Application user identity accounts linked to specific Oracle XE database security roles.",
    relations: [
      { target: "AUDIT_LOG", type: "||--o{", label: "audited actions", meaning: "Performs 0..N auditable actions" }
    ]
  },
  {
    name: "AUDIT_LOG",
    domain: "Security",
    pks: ["audit_id"],
    fks: ["user_id"],
    desc: "Immutable compliance audit trail tracking all INSERT, UPDATE, and DELETE operations.",
    relations: [
      { target: "APP_USER", type: "}o--o|", label: "performed by", meaning: "Optionally linked to 1 app user account" }
    ]
  },
  {
    name: "ML_PREDICTION",
    domain: "AI / ML",
    pks: ["prediction_id"],
    fks: ["appointment_id", "run_id"],
    desc: "No-show risk score per (appointment, model run), MERGEd by the ML pipeline, with the top risk factors. v2: patient_id and model name/version removed (transitive dependencies).",
    relations: [
      { target: "APPOINTMENT", type: "}o--||", label: "scheduled appointment", meaning: "Evaluates 1 specific appointment (patient reached through it)" },
      { target: "ML_MODEL_RUN", type: "}o--||", label: "produced by", meaning: "Produced by exactly 1 registered model run" }
    ]
  },
  {
    name: "ML_MODEL_RUN",
    domain: "AI / ML",
    pks: ["run_id"],
    fks: [],
    desc: "Model registry: one row per training run with test metrics and a JSON report; a unique function-based index allows only one active model.",
    relations: [
      { target: "ML_PREDICTION", type: "||--o{", label: "produces", meaning: "One run produces 0..N predictions" }
    ]
  },
  {
    name: "DISEASE",
    domain: "Clinical",
    pks: ["disease_code"],
    fks: [],
    desc: "ICD-10 reference table (natural key). Split out of DIAGNOSIS in v2 to remove the transitive dependency disease_code → disease_name.",
    relations: [
      { target: "DIAGNOSIS", type: "||--o{", label: "classifies", meaning: "One disease code classifies 0..N diagnoses" }
    ]
  }
];

let renderCounter = 0;

export default function ErModelPage() {
  const containerRef = useRef(null);
  const [activeTab, setActiveTab] = useState("MASTER");
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTable, setSelectedTable] = useState(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [showNotationModal, setShowNotationModal] = useState(false);

  // Apply high-contrast styling and fix invisible/white text in Mermaid ER tables
  const applySvgStylesAndListeners = useCallback((svgEl) => {
    if (!svgEl) return;

    // 1. Fix: Ensure entity table headers are deep teal with bold white text
    svgEl.querySelectorAll(".entityLabel, text.entityLabel, g.entityBox text:first-of-type").forEach((el) => {
      el.setAttribute("fill", "#ffffff");
      el.style.fill = "#ffffff";
      el.style.fontWeight = "700";
      el.style.fontSize = "13px";
    });

    // 2. Fix: Ensure attribute cell text (column name, datatype, PK/FK) is DARK SLATE and visible!
    svgEl.querySelectorAll("text:not(.entityLabel)").forEach((el) => {
      const textVal = el.textContent?.trim();
      if (textVal === "PK" || textVal === "FK" || textVal === "PK_FK") {
        el.setAttribute("fill", "#0f766e");
        el.style.fill = "#0f766e";
        el.style.fontWeight = "800";
        el.style.fontSize = "11px";
      } else {
        el.setAttribute("fill", "#0f172a");
        el.style.fill = "#0f172a";
        el.style.fontWeight = "500";
        el.style.fontSize = "12px";
      }
    });

    // 3. Fix: Ensure table cell rectangles are clean white/light gray with slate borders
    svgEl.querySelectorAll(".attributeBoxOdd, rect[class*='attributeBoxOdd']").forEach((el) => {
      el.setAttribute("fill", "#f8fafc");
      el.setAttribute("stroke", "#cbd5e1");
      el.style.fill = "#f8fafc";
      el.style.stroke = "#cbd5e1";
    });
    svgEl.querySelectorAll(".attributeBoxEven, rect[class*='attributeBoxEven']").forEach((el) => {
      el.setAttribute("fill", "#ffffff");
      el.setAttribute("stroke", "#cbd5e1");
      el.style.fill = "#ffffff";
      el.style.stroke = "#cbd5e1";
    });

    // 4. Fix: Entity header rect styling
    svgEl.querySelectorAll(".entityBox, rect.entityBox").forEach((el) => {
      el.setAttribute("fill", "#0f594a");
      el.setAttribute("stroke", "#0d5c4d");
      el.style.fill = "#0f594a";
      el.style.stroke = "#0d5c4d";
    });

    // 5. Fix: Relationship lines and markers
    svgEl.querySelectorAll("path.relationshipLine, .er.relationshipLine").forEach((el) => {
      el.setAttribute("stroke", "#0f766e");
      el.setAttribute("stroke-width", "2");
      el.style.stroke = "#0f766e";
      el.style.strokeWidth = "2px";
    });

    // 6. Interactive Click Listener: Clicking an entity in the SVG diagram highlights it and opens its catalog entry
    svgEl.querySelectorAll("g").forEach((g) => {
      const label = g.querySelector(".entityLabel, text")?.textContent?.trim().toUpperCase();
      if (label && TABLE_METADATA.some((t) => t.name === label)) {
        g.style.cursor = "pointer";
        g.onclick = (e) => {
          e.stopPropagation();
          const match = TABLE_METADATA.find((t) => t.name === label);
          if (match) setSelectedTable(match);
        };
      }
    });
  }, []);

  // Highlight selected entity in SVG and center it
  const highlightEntityInSvg = useCallback((tableName) => {
    const svgEl = containerRef.current?.querySelector("svg");
    if (!svgEl) return;

    // Reset previous entity highlights
    svgEl.querySelectorAll("g[id*='entity-'], g.entityBox, g").forEach((g) => {
      const isEntity = g.querySelector(".entityLabel");
      if (isEntity) {
        g.style.opacity = "1";
        g.style.filter = "none";
        const headerRect = g.querySelector("rect.entityBox, rect");
        if (headerRect) {
          headerRect.style.stroke = "#0d5c4d";
          headerRect.style.strokeWidth = "1.5px";
        }
      }
    });

    if (!tableName) return;

    // Locate the matching entity <g>
    let targetG = null;
    svgEl.querySelectorAll("g").forEach((g) => {
      const label = g.querySelector(".entityLabel, text")?.textContent?.trim().toUpperCase();
      const id = (g.getAttribute("id") || "").toUpperCase();
      if (label === tableName || id.includes(`ENTITY-${tableName}-`) || id === `ENTITY-${tableName}`) {
        targetG = g;
      }
    });

    if (targetG) {
      // Dim other entities
      svgEl.querySelectorAll("g").forEach((g) => {
        const isEntity = g.querySelector(".entityLabel");
        if (isEntity && g !== targetG) {
          g.style.opacity = "0.3";
          g.style.transition = "opacity 0.25s ease";
        }
      });

      // Highlight the target entity with glowing pulse & vibrant cyan border
      targetG.style.opacity = "1";
      targetG.style.filter = "drop-shadow(0 0 18px rgba(45, 212, 191, 0.95)) drop-shadow(0 0 4px rgba(15, 118, 110, 0.8))";
      targetG.style.transition = "all 0.25s ease";
      const headerRect = targetG.querySelector("rect.entityBox, rect");
      if (headerRect) {
        headerRect.style.stroke = "#2dd4bf";
        headerRect.style.strokeWidth = "3.5px";
      }

      // Smooth scroll the container to center on this entity
      targetG.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    }
  }, []);

  // Render diagram on active tab change
  const renderDiagram = useCallback(async (tabKey) => {
    setLoading(true);
    setError(null);
    try {
      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        themeVariables: {
          fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
          fontSize: "13px",
          primaryColor: "#0f594a",
          primaryTextColor: "#ffffff",
          primaryBorderColor: "#14725f",
          lineColor: "#0f766e",
          secondaryColor: "#14725f",
          tertiaryColor: "#f0fdfa",
          attributeBackgroundColorOdd: "#f8fafc",
          attributeBackgroundColorEven: "#ffffff",
          attributeTextColor: "#0f172a",
          entityBorderColor: "#0d5c4d",
          entityTextColor: "#0f172a",
          entityHeadingColor: "#ffffff",
          nodeBorder: "#0d5c4d",
        },
        securityLevel: "loose",
        er: {
          useMaxWidth: false,
          diagramPadding: 28,
          entityPadding: 18,
          layoutDirection: "TB",
          minEntityWidth: 140,
          minEntityHeight: 80,
        },
      });

      const diagramSource = ER_DIAGRAMS[tabKey];
      const uniqueId = `er-diagram-${tabKey.toLowerCase()}-${++renderCounter}`;
      const { svg } = await mermaid.render(uniqueId, diagramSource);

      if (containerRef.current) {
        containerRef.current.innerHTML = svg;
        const svgEl = containerRef.current.querySelector("svg");
        if (svgEl) {
          svgEl.style.width = "100%";
          svgEl.style.height = "auto";
          svgEl.style.minWidth = tabKey === "MASTER" ? "1400px" : "900px";
          svgEl.style.display = "block";
          applySvgStylesAndListeners(svgEl);
        }
      }
    } catch (err) {
      console.error("Mermaid ER rendering error:", err);
      setError(err?.message || "Failed to render ER diagram");
    } finally {
      setLoading(false);
    }
  }, [applySvgStylesAndListeners]);

  useEffect(() => {
    renderDiagram(activeTab);
  }, [activeTab, renderDiagram]);

  // When selectedTable changes, trigger diagram highlight
  useEffect(() => {
    if (selectedTable) {
      highlightEntityInSvg(selectedTable.name);
    } else {
      highlightEntityInSvg(null);
    }
  }, [selectedTable, highlightEntityInSvg]);

  // Zoom handlers
  const handleZoomIn = () => setZoom((z) => Math.min(2.0, +(z + 0.15).toFixed(2)));
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)));
  const handleResetZoom = () => setZoom(1);

  // SVG Export Download Handler
  const handleDownloadSvg = () => {
    const svgEl = containerRef.current?.querySelector("svg");
    if (!svgEl) return;
    const serializer = new XMLSerializer();
    const svgBlob = new Blob([serializer.serializeToString(svgEl)], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `medicore_hcms_erd_${activeTab.toLowerCase()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const filteredTables = TABLE_METADATA.filter(
    (t) =>
      t.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      t.domain.toLowerCase().includes(searchFilter.toLowerCase()) ||
      t.desc.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className={`space-y-6 ${fullscreen ? "fixed inset-0 z-50 bg-[#f8faf9] p-6 overflow-y-auto" : ""}`}>
      {/* Page Header with Stats & Crow's Foot Guide Trigger */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 text-xs font-semibold tracking-wider uppercase text-accent mb-1">
            <Database size={15} />
            <span>Relational Schema Architecture</span>
          </div>
          <h1 className="text-3xl font-display font-semibold text-ink leading-tight m-0">
            Entity-Relationship Model
          </h1>
          <p className="text-sm text-ink-muted mt-1 max-w-2xl">
            Formal 3NF/BCNF relational model for Oracle XE. Click any table in the diagram or catalog below to highlight it and inspect its Crow's Foot cardinality.
          </p>
        </div>

        {/* Action Buttons & Schema Metrics */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setShowNotationModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 rounded-lg shadow-2xs transition"
          >
            <Info size={14} className="text-teal-700" />
            <span>Crow's Foot Notation Guide</span>
          </button>
          <div className="px-3 py-1.5 rounded-lg bg-surface border border-border shadow-xs text-xs text-ink-muted flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <strong className="text-ink font-semibold">28</strong> Entities
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-surface border border-border shadow-xs text-xs text-ink-muted flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-teal-500" />
            <strong className="text-ink font-semibold">27</strong> Relationships
          </div>
        </div>
      </div>

      {/* Domain Navigation Tabs */}
      <div className="flex items-center gap-1.5 p-1 bg-surface-alt/70 border border-border rounded-xl overflow-x-auto">
        {[
          { key: "MASTER", label: "Master ERD (All 28 Tables)", icon: Layers },
          { key: "CLINICAL", label: "Clinical & Diagnosis", icon: GitBranch },
          { key: "ADMISSION", label: "Inpatient & Facilities", icon: Table },
          { key: "PHARMACY_LAB", label: "Pharmacy & Diagnostics", icon: Database },
          { key: "FINANCIAL", label: "Billing & Queue Operations", icon: CheckCircle2 },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setActiveTab(key); handleResetZoom(); }}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg whitespace-nowrap transition-all duration-150 ${
              activeTab === key
                ? "bg-white text-accent font-semibold shadow-xs border border-border"
                : "text-ink-muted hover:text-ink hover:bg-white/50"
            }`}
          >
            <Icon size={14} className={activeTab === key ? "text-accent" : "text-ink-faint"} />
            {label}
          </button>
        ))}
      </div>

      {/* Diagram Canvas Container */}
      <div className="bg-white border border-border rounded-2xl shadow-sm overflow-hidden flex flex-col">
        {/* Canvas Toolbar */}
        <div className="px-4 py-3 bg-[#fcfdfd] border-b border-border flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="font-semibold text-ink">Active Domain:</span>
            <span className="px-2.5 py-0.5 rounded-full bg-teal-50 text-accent font-mono text-[0.72rem] font-medium border border-teal-200/60">
              {activeTab}
            </span>
            {selectedTable && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-accent text-white font-mono text-[0.72rem] font-semibold animate-fade">
                <Sparkles size={11} /> Highlighted: {selectedTable.name}
              </span>
            )}
          </div>

          {/* Interactive Zoom & Export Controls */}
          <div className="flex items-center gap-1.5">
            <div className="flex items-center bg-surface border border-border rounded-lg p-0.5 shadow-2xs">
              <button
                onClick={handleZoomOut}
                title="Zoom Out"
                className="p-1.5 rounded-md hover:bg-surface-alt text-ink-muted hover:text-ink transition"
              >
                <ZoomOut size={15} />
              </button>
              <button
                onClick={handleResetZoom}
                title="Reset Zoom"
                className="px-2 py-1 text-xs font-mono font-medium text-ink-muted hover:text-ink transition hover:bg-surface-alt rounded-md"
              >
                {Math.round(zoom * 100)}%
              </button>
              <button
                onClick={handleZoomIn}
                title="Zoom In"
                className="p-1.5 rounded-md hover:bg-surface-alt text-ink-muted hover:text-ink transition"
              >
                <ZoomIn size={15} />
              </button>
            </div>

            <button
              onClick={handleDownloadSvg}
              title="Download Vector SVG"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface border border-border hover:bg-surface-alt text-ink rounded-lg shadow-2xs transition"
            >
              <Download size={14} />
              <span className="hidden sm:inline">Export SVG</span>
            </button>

            <button
              onClick={() => setFullscreen((f) => !f)}
              title={fullscreen ? "Exit Fullscreen" : "Fullscreen View"}
              className="p-2 text-ink-muted hover:text-ink bg-surface border border-border hover:bg-surface-alt rounded-lg shadow-2xs transition"
            >
              {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
          </div>
        </div>

        {/* Scrollable Diagram Canvas with Zoom Transform */}
        <div className="relative p-6 overflow-auto bg-[#fafcfb] min-h-[520px] max-h-[720px] flex items-center justify-center er-svg-wrap">
          {loading && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/80 backdrop-blur-xs text-xs text-ink-muted">
              <div className="w-8 h-8 border-3 border-accent/20 border-t-accent rounded-full animate-spin mb-3" />
              <span>Rendering authoritative schema diagram...</span>
            </div>
          )}

          {error ? (
            <div className="p-6 text-center max-w-md">
              <HelpCircle size={32} className="mx-auto text-urgent mb-2 opacity-80" />
              <div className="text-sm font-semibold text-ink">Diagram Render Notice</div>
              <p className="text-xs text-ink-muted mt-1">{error}</p>
            </div>
          ) : (
            <div
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: "center top",
                transition: "transform 0.15s ease-out",
              }}
              className="w-full flex justify-center"
            >
              <div ref={containerRef} className="w-full" />
            </div>
          )}
        </div>

        {/* Cardinality Quick-Reference Footer */}
        <div className="px-5 py-3 bg-[#f8faf9] border-t border-border flex items-center justify-between text-xs text-ink-muted flex-wrap gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold text-ink">Crow's Foot Symbols:</span>
            {CROWS_FOOT_SYMBOLS.map((s) => (
              <span
                key={s.code}
                onClick={() => setShowNotationModal(true)}
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-white border border-border hover:border-teal-400 cursor-pointer transition text-[0.72rem]"
              >
                <span className="font-mono font-bold text-accent">{s.symbolText}</span>
                <span className="text-ink-muted">{s.name}</span>
              </span>
            ))}
          </div>
          <div className="text-[0.7rem] text-ink-faint">
            Schema Owner: <code className="bg-surface px-1.5 py-0.5 rounded border border-border">HCMS_ADMIN</code> • Oracle XE
          </div>
        </div>
      </div>

      {/* Selected Entity Inspector & Active Relationships Banner */}
      {selectedTable && (
        <div className="p-5 rounded-2xl bg-teal-50/50 border border-teal-300 ring-2 ring-teal-500/15 shadow-sm animate-fade">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-mono font-bold text-lg text-teal-950">{selectedTable.name}</span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-teal-600 text-white font-semibold">
                  {selectedTable.domain} Domain
                </span>
                <span className="text-xs text-teal-700 font-mono">
                  PK: {selectedTable.pks.join(", ") || "None"}
                </span>
              </div>
              <p className="text-xs text-teal-900 mt-1 m-0">{selectedTable.desc}</p>
            </div>
            <button
              onClick={() => setSelectedTable(null)}
              className="text-xs text-teal-700 hover:text-teal-950 font-medium px-2.5 py-1 rounded bg-white/70 hover:bg-white border border-teal-200 transition"
            >
              Clear highlight
            </button>
          </div>

          {/* Active Relational Connections & Cardinality */}
          <div className="mt-3 pt-3 border-t border-teal-200/70">
            <div className="text-[0.75rem] font-semibold text-teal-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <GitBranch size={13} className="text-teal-700" />
              Connected Relational Foreign Keys &amp; Cardinality:
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {selectedTable.relations.map((rel, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    const targetMatch = TABLE_METADATA.find((t) => t.name === rel.target);
                    if (targetMatch) setSelectedTable(targetMatch);
                  }}
                  className="p-2.5 rounded-lg bg-white border border-teal-200/80 hover:border-teal-400 hover:shadow-xs transition cursor-pointer flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between text-xs font-mono font-semibold text-teal-950 mb-1">
                    <span>{selectedTable.name}</span>
                    <span className="text-[0.7rem] px-1.5 py-0.2 rounded bg-teal-100 text-teal-800">
                      {rel.type}
                    </span>
                    <span className="text-accent hover:underline">{rel.target}</span>
                  </div>
                  <div className="text-[0.72rem] text-ink-muted">
                    {rel.meaning}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Interactive Entity Catalog & Table Dictionary */}
      <div className="bg-surface border border-border rounded-2xl p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div>
            <h2 className="text-lg font-display font-semibold text-ink m-0 flex items-center gap-2">
              <Table size={18} className="text-accent" />
              Relational Entity Catalog &amp; Dictionary (28 Tables)
            </h2>
            <p className="text-xs text-ink-muted mt-0.5">
              Click any entity card below to highlight it directly on the diagram canvas and view its Crow's Foot relationships.
            </p>
          </div>

          {/* Quick Search Filter */}
          <div className="relative w-full sm:w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              type="text"
              placeholder="Search 28 schema tables..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-border rounded-lg outline-none focus:border-accent focus:ring-2 focus:ring-accent/15 transition"
            />
          </div>
        </div>

        {/* Tables Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {filteredTables.map((table) => {
            const isSelected = selectedTable?.name === table.name;
            return (
              <div
                key={table.name}
                onClick={() => setSelectedTable(isSelected ? null : table)}
                className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                  isSelected
                    ? "bg-teal-50 border-teal-300 ring-2 ring-teal-500/20 shadow-xs"
                    : "bg-white border-border hover:border-teal-400/80 hover:shadow-xs"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-ink">{table.name}</span>
                    <span className="text-[0.65rem] px-1.5 py-0.2 rounded-full font-medium bg-surface-alt text-ink-muted border border-border">
                      {table.domain}
                    </span>
                  </div>
                  <ChevronRight size={14} className={`text-ink-faint transition-transform ${isSelected ? "rotate-90 text-accent font-bold" : ""}`} />
                </div>

                <p className="text-[0.75rem] text-ink-muted line-clamp-2 m-0 mb-2.5">
                  {table.desc}
                </p>

                <div className="flex items-center justify-between text-[0.68rem] font-mono text-ink-faint border-t border-border/60 pt-2">
                  <span className="text-teal-700 font-semibold">PK: {table.pks.join(", ")}</span>
                  <span className="text-sky-700 font-semibold">
                    {table.relations.length} relations
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Crow's Foot Notation Modal Guide */}
      {showNotationModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fade">
          <div className="bg-white rounded-2xl max-w-2xl w-full border border-border shadow-xl p-6 overflow-hidden">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-teal-50 text-accent">
                  <GitBranch size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-display font-semibold text-ink m-0">Crow's Foot ER Notation Guide</h3>
                  <p className="text-xs text-ink-muted m-0">Standard Information Engineering (IE) cardinality &amp; modality reference</p>
                </div>
              </div>
              <button
                onClick={() => setShowNotationModal(false)}
                className="text-xs px-2.5 py-1 rounded-md text-ink-muted hover:text-ink hover:bg-surface-alt font-medium"
              >
                Close ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 max-h-[60vh] overflow-y-auto pr-1">
              <p className="text-xs text-ink-muted leading-relaxed">
                In Crow's Foot ER modeling, each relationship connector has two markers at each end:
                the <strong>inner symbol</strong> indicates the <strong>minimum cardinality (modality)</strong> (0 = Optional, 1 = Mandatory),
                while the <strong>outer symbol</strong> indicates the <strong>maximum cardinality</strong> (1 = Single, Crow's Foot = Many).
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                {CROWS_FOOT_SYMBOLS.map((s) => (
                  <div key={s.code} className="p-3.5 rounded-xl border border-border bg-[#fafcfb] flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-sm font-bold text-accent bg-teal-50 px-2 py-0.5 rounded border border-teal-200/50">
                          {s.symbolText}
                        </span>
                        {s.svgPath}
                      </div>
                      <div className="text-xs font-semibold text-ink">{s.name}</div>
                      <div className="text-[0.68rem] text-teal-700 font-mono mb-1.5">{s.altName} (Min: {s.min}, Max: {s.max})</div>
                      <p className="text-[0.75rem] text-ink-muted m-0">{s.description}</p>
                    </div>
                    <div className="mt-2.5 pt-2 border-t border-border/60 text-[0.7rem] text-ink-faint italic">
                      e.g., {s.example}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-border flex justify-end">
              <button
                onClick={() => setShowNotationModal(false)}
                className="px-4 py-2 text-xs font-semibold bg-accent text-white rounded-lg hover:bg-accent/90 transition"
              >
                Got it, close guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}