import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import { panelCls, panelHeadCls } from "../components/ui";
import { KeyRound, Link2, Layers, Search, CheckCircle2, AlertTriangle, GitBranch } from "lucide-react";

// ---------------------------------------------------------------------------
// Keys and functional dependencies of every table (28).
// nf: "BCNF" = every determinant is a candidate key.
//     "3NF*" = BCNF/3NF except a DOCUMENTED, trigger-protected redundancy.
// ---------------------------------------------------------------------------
const T = [
  { t: "DEPARTMENT", pk: "department_id", ck: ["department_name"], fk: ["head_doctor_id → DOCTOR"], fd: ["department_id → department_name, head_doctor_id, location, created_at", "department_name → department_id"], nf: "BCNF", note: "Circular FK with DOCTOR (head of department) is added with ALTER TABLE after both tables exist." },
  { t: "DOCTOR", pk: "doctor_id", ck: ["license_no", "email"], fk: ["department_id → DEPARTMENT"], fd: ["doctor_id → first_name, last_name, department_id, specialization, qualification, license_no, phone, email, consultation_fee, joining_date", "license_no → doctor_id", "email → doctor_id"], nf: "BCNF", note: "specialization does NOT determine department (two departments can share one), so there is no transitive dependency." },
  { t: "NURSE", pk: "nurse_id", ck: ["license_no", "email"], fk: ["department_id → DEPARTMENT"], fd: ["nurse_id → all attributes", "license_no → nurse_id"], nf: "BCNF" },
  { t: "PATIENT", pk: "patient_id", ck: ["email (UNIQUE, optional)"], fk: [], fd: ["patient_id → first_name, last_name, dob, gender, blood_group, phone, email, address, city, emergency_contact_name, emergency_contact_phone, registered_date"], nf: "BCNF", note: "age is DERIVED from dob (calculate_age) and never stored. v2: city split out of the free-text address (atomic values, 1NF)." },
  { t: "ROOM_BED", pk: "room_bed_id", ck: ["(room_no, bed_no)"], fk: ["department_id → DEPARTMENT"], fd: ["room_bed_id → room_no, bed_no, department_id, room_type, status, daily_rate", "(room_no, bed_no) → room_bed_id"], nf: "BCNF", note: "Business rule: type and rate belong to the BED (a room can mix ICU cubicles and general beds). If the rule were 'room_no → room_type, daily_rate' this would be a partial dependency on the candidate key → split into ROOM(room_no, …) and BED(room_bed_id, room_no, bed_no, status) — see the worked example below." },
  { t: "STAFF_SCHEDULE", pk: "schedule_id", ck: ["(doctor_id, schedule_date, start_time)"], fk: ["doctor_id → DOCTOR (ON DELETE CASCADE)"], fd: ["schedule_id → doctor_id, schedule_date, start_time, end_time, max_patients"], nf: "BCNF" },
  { t: "APPOINTMENT", pk: "appointment_id", ck: ["(doctor_id, appt_date, appt_time)", "(patient_id, appt_date, appt_time)"], fk: ["patient_id → PATIENT", "doctor_id → DOCTOR"], fd: ["appointment_id → patient_id, doctor_id, appt_date, appt_time, appt_type, status, reason, created_at", "each candidate key → appointment_id"], nf: "BCNF", note: "Two overlapping candidate keys - every determinant is still a key, so BCNF holds." },
  { t: "ADMISSION", pk: "admission_id", ck: [], fk: ["patient_id → PATIENT", "room_bed_id → ROOM_BED", "admitting_doctor_id → DOCTOR"], fd: ["admission_id → all attributes"], nf: "BCNF" },
  { t: "SYMPTOM", pk: "symptom_id", ck: ["symptom_name"], fk: [], fd: ["symptom_id ↔ symptom_name"], nf: "BCNF" },
  { t: "DISEASE", pk: "disease_code (ICD-10, natural key)", ck: [], fk: [], fd: ["disease_code → disease_name, is_chronic"], nf: "BCNF", note: "NEW in v2 - removed the transitive dependency diagnosis_id → disease_code → disease_name from DIAGNOSIS." },
  { t: "DIAGNOSIS", pk: "diagnosis_id", ck: [], fk: ["patient_id → PATIENT", "doctor_id → DOCTOR", "appointment_id → APPOINTMENT", "admission_id → ADMISSION", "disease_code → DISEASE"], fd: ["diagnosis_id → patient_id, doctor_id, appointment_id, admission_id, disease_code, severity, diagnosis_date", "appointment_id → patient_id (via APPOINTMENT)"], nf: "3NF*", note: "Exclusive arc: exactly one of appointment_id / admission_id (CHECK). patient_id is redundant through the encounter but kept so look-ups do not need a 2-way join; trg_diagnosis_encounter_chk guarantees it always matches." },
  { t: "DIAGNOSIS_SYMPTOM", pk: "(diagnosis_id, symptom_id)", ck: [], fk: ["diagnosis_id → DIAGNOSIS (CASCADE)", "symptom_id → SYMPTOM"], fd: ["all-key relation - no non-trivial FDs"], nf: "BCNF", note: "Bridge table resolving the M:N relationship DIAGNOSIS - SYMPTOM." },
  { t: "VITAL_SIGN", pk: "vital_id", ck: [], fk: ["patient_id, appointment_id, admission_id"], fd: ["vital_id → recorded_at, temperature_c, pulse_rate, systolic_bp, diastolic_bp, spo2_percent, height_cm, weight_kg, …"], nf: "3NF*", note: "BMI is derived (calculate_bmi) and never stored. Same trigger-protected patient_id redundancy as DIAGNOSIS." },
  { t: "CLINICAL_NOTE", pk: "note_id", ck: [], fk: ["patient_id, doctor_id, appointment_id, admission_id"], fd: ["note_id → all attributes"], nf: "3NF*", note: "trg_note_encounter_chk keeps patient_id consistent." },
  { t: "MEDICINE", pk: "medicine_id", ck: ["medicine_code"], fk: [], fd: ["medicine_id → medicine_code, medicine_name, category, unit_price, stock_quantity, reorder_level, expiry_date"], nf: "BCNF" },
  { t: "PRESCRIPTION", pk: "prescription_id", ck: [], fk: ["patient_id, doctor_id, appointment_id"], fd: ["prescription_id → patient_id, doctor_id, appointment_id, prescribed_date, status"], nf: "3NF*", note: "appointment_id is optional (walk-in prescriptions), so patient_id must be stored; consistency trigger when both are present." },
  { t: "PRESCRIPTION_ITEM", pk: "prescription_item_id", ck: ["(prescription_id, medicine_id)"], fk: ["prescription_id → PRESCRIPTION (CASCADE)", "medicine_id → MEDICINE"], fd: ["prescription_item_id → prescription_id, medicine_id, dosage, duration_days, quantity"], nf: "BCNF", note: "unit_price is NOT copied here - it is read from MEDICINE." },
  { t: "LAB_TEST_CATALOG", pk: "lab_test_id", ck: ["test_code"], fk: [], fd: ["lab_test_id → test_code, test_name, normal_range, price"], nf: "BCNF" },
  { t: "LAB_ORDER", pk: "lab_order_id", ck: [], fk: ["patient_id, doctor_id, lab_test_id"], fd: ["lab_order_id → patient_id, doctor_id, lab_test_id, order_date, status, result_value, result_date"], nf: "BCNF" },
  { t: "INSURANCE_POLICY", pk: "policy_id", ck: ["patient_id", "policy_no"], fk: ["patient_id → PATIENT"], fd: ["policy_id → patient_id, policy_no, provider_name, coverage_amount, valid_until"], nf: "BCNF", note: "UNIQUE(patient_id) implements the 1 : 0..1 relationship instead of nullable columns in PATIENT." },
  { t: "BILL", pk: "bill_id", ck: [], fk: ["patient_id, appointment_id, admission_id"], fd: ["bill_id → patient_id, appointment_id, admission_id, bill_date, status"], nf: "3NF*", note: "Bill total and balance are DERIVED (calculate_bill_total / fn_bill_balance / views), never stored - storing them would create an update anomaly." },
  { t: "BILL_ITEM", pk: "bill_item_id", ck: [], fk: ["bill_id → BILL (CASCADE)"], fd: ["bill_item_id → bill_id, item_description, item_category, amount"], nf: "BCNF", note: "amount is a historical SNAPSHOT of the price at billing time (later price changes must not alter old bills) - this is not redundancy." },
  { t: "PAYMENT", pk: "payment_id", ck: [], fk: ["bill_id → BILL"], fd: ["payment_id → bill_id, amount_paid, payment_mode, paid_date"], nf: "BCNF" },
  { t: "SERVICE_QUEUE", pk: "queue_id", ck: ["(queue_type, queue_date, queue_number)"], fk: ["patient_id, doctor_id, department_id"], fd: ["queue_id → all attributes", "doctor_id → department_id (when a doctor is assigned)"], nf: "3NF*", note: "department_id is needed for department-level queues that have no doctor; when a doctor is present it duplicates DOCTOR.department_id (documented, set by book_appointment)." },
  { t: "APP_USER", pk: "user_id", ck: ["username"], fk: ["linked_doctor_id / linked_nurse_id / linked_patient_id"], fd: ["user_id → username, role_name, links, is_active, created_at"], nf: "BCNF", note: "EER category (union type): an account is linked to at most one of doctor / nurse / patient (CHECK)." },
  { t: "AUDIT_LOG", pk: "audit_id", ck: [], fk: ["user_id → APP_USER"], fd: ["audit_id → user_id, table_name, record_id, operation, old_value, new_value, action_timestamp"], nf: "BCNF", note: "Append-only history; even ADMIN_ROLE has SELECT only." },
  { t: "ML_MODEL_RUN", pk: "run_id", ck: ["(model_name, model_version)"], fk: [], fd: ["run_id → model_name, model_version, trained_at, rows, dates, threshold, metrics, is_active, metrics_json"], nf: "BCNF", note: "metrics_json is stored and used as ONE opaque document (CHECK IS JSON); every metric that is queried is also an atomic column." },
  { t: "ML_PREDICTION", pk: "prediction_id", ck: ["(appointment_id, run_id)"], fk: ["appointment_id → APPOINTMENT", "run_id → ML_MODEL_RUN"], fd: ["prediction_id → appointment_id, run_id, prediction, probability, risk_factors, prediction_date"], nf: "BCNF", note: "v2: patient_id (appointment_id → patient_id) and model_name/model_version (run_id → …) removed - they were transitive dependencies." },
];

const STEPS = [
  { nf: "UNF", title: "Un-normalised 'visit sheet'", rel: "VISIT(appointment_id, appt_date, patient_name, patient_phone, doctor_name, department_name, dept_location, { disease_code, disease_name }, { medicine_code, medicine_name, unit_price, dosage, qty })", problem: "Repeating groups { … } - one visit has several diagnoses and several medicines in one row." },
  { nf: "1NF", title: "Atomic values, no repeating groups", rel: "VISIT_LINE(appointment_id, medicine_code, appt_date, patient_id, patient_name, patient_phone, doctor_id, doctor_name, department_id, department_name, dept_location, medicine_name, unit_price, dosage, qty)   key = (appointment_id, medicine_code)", problem: "Partial dependencies: appointment_id → patient_name, doctor_name …;  medicine_code → medicine_name, unit_price. Update anomaly: changing a price means updating every line that ever used it." },
  { nf: "2NF", title: "Remove partial dependencies", rel: "APPOINTMENT(appointment_id, appt_date, patient_id, patient_name, patient_phone, doctor_id, doctor_name, department_id, department_name, dept_location)\nMEDICINE(medicine_code, medicine_name, unit_price)\nPRESCRIPTION_ITEM(appointment_id, medicine_code, dosage, qty)", problem: "Transitive dependencies remain: appointment_id → patient_id → patient_name;  appointment_id → doctor_id → department_id → dept_location;  diagnosis → disease_code → disease_name." },
  { nf: "3NF", title: "Remove transitive dependencies", rel: "PATIENT(patient_id, name, phone, …)   DOCTOR(doctor_id, name, department_id)   DEPARTMENT(department_id, name, location)\nAPPOINTMENT(appointment_id, patient_id, doctor_id, appt_date, appt_time)\nDISEASE(disease_code, disease_name)   DIAGNOSIS(diagnosis_id, appointment_id, disease_code, severity)\nMEDICINE(…)   PRESCRIPTION(…)   PRESCRIPTION_ITEM(…)", problem: "Every non-key attribute now depends on the key, the whole key and nothing but the key." },
  { nf: "BCNF", title: "Every determinant is a candidate key", rel: "Check the remaining FDs: APPOINTMENT has candidate keys appointment_id, (doctor_id, appt_date, appt_time), (patient_id, appt_date, appt_time) - all determinants are keys ✓.\nROOM_BED: IF room_no → room_type, daily_rate held, room_no would be a determinant that is not a key → decompose into ROOM(room_no, department_id, room_type, daily_rate) + BED(room_bed_id, room_no, bed_no, status).", problem: "This schema applies the per-bed rule, so ROOM_BED is already in BCNF; the decomposition shows what changes if the hospital's rule changes." },
];

const MAPPING = [
  ["Strong entity", "Table with surrogate PK (sequence DEFAULT) - PATIENT, DOCTOR, MEDICINE …"],
  ["1 : N relationship", "FK on the N side - APPOINTMENT.doctor_id → DOCTOR"],
  ["M : N relationship", "Bridge table with composite PK - DIAGNOSIS_SYMPTOM(diagnosis_id, symptom_id)"],
  ["1 : 0..1 relationship", "FK + UNIQUE - INSURANCE_POLICY.patient_id"],
  ["Recursive / circular", "DEPARTMENT.head_doctor_id → DOCTOR while DOCTOR.department_id → DEPARTMENT (FK added by ALTER TABLE)"],
  ["Weak / dependent entity", "BILL_ITEM, PRESCRIPTION_ITEM - ON DELETE CASCADE from their owner"],
  ["Exclusive arc", "DIAGNOSIS belongs to an APPOINTMENT XOR an ADMISSION - CHECK chk_diag_one_encounter"],
  ["EER specialisation", "STAFF ⊃ {DOCTOR, NURSE} (disjoint, partial) mapped as one table per subclass (no superclass table)"],
  ["EER category (union)", "APP_USER may represent a DOCTOR, a NURSE or a PATIENT - three nullable FKs + CHECK (at most one)"],
  ["Derived attributes", "age, BMI, bill total, balance - computed by PL/SQL functions / views, never stored"],
  ["Multivalued attribute", "symptoms of a diagnosis → separate table instead of a list column"],
];

export default function NormalizationPage() {
  const [q, setQ] = useState("");
  const list = useMemo(() => T.filter((x) => !q || (x.t + x.fd.join(" ") + (x.note || "")).toLowerCase().includes(q.toLowerCase())), [q]);
  const counts = useMemo(() => T.reduce((a, x) => ({ ...a, [x.nf]: (a[x.nf] || 0) + 1 }), {}), []);
  return (
    <div>
      <PageHeader title="Keys, functional dependencies & normalization"
        subtitle={`All ${T.length} tables: primary / candidate / foreign keys, the functional dependencies that hold, and the normal form reached. ${counts["BCNF"]} tables are in BCNF; ${counts["3NF*"]} carry a documented, trigger-protected redundancy.`}
        actions={<Link to="/er-model" className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft"><GitBranch size={15} /> ER model</Link>} />

      <div className={panelCls}>
        <div className={panelHeadCls}><h2 className="text-lg font-display m-0 flex items-center gap-2"><Layers size={18} className="text-accent" /> Normalization walk-through (UNF → BCNF)</h2></div>
        <div className="space-y-3">
          {STEPS.map((s) => (
            <div key={s.nf} className="grid md:grid-cols-[90px_1fr] gap-3 border border-border rounded-lg p-3.5">
              <div className="font-display text-xl font-semibold text-accent-strong">{s.nf}</div>
              <div>
                <div className="font-medium text-sm">{s.title}</div>
                <pre className="bg-surface-2 border border-border rounded-md p-2.5 text-[0.75rem] font-mono whitespace-pre-wrap my-2">{s.rel}</pre>
                <div className="text-xs text-ink-muted">{s.problem}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}><h2 className="text-lg font-display m-0">ER / EER → relational mapping rules used</h2></div>
        <table className="w-full text-sm">
          <tbody>{MAPPING.map(([k, v]) => (
            <tr key={k} className="border-b border-border/70"><td className="py-2 pr-4 font-medium whitespace-nowrap align-top">{k}</td><td className="py-2 text-ink-muted">{v}</td></tr>
          ))}</tbody>
        </table>
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><KeyRound size={18} className="text-accent" /> Per-table keys and FDs</h2>
          <div className="flex items-center gap-2 border border-border rounded-md px-2.5 py-1.5"><Search size={14} className="text-ink-muted" /><input className="outline-none text-sm bg-transparent" placeholder="Filter…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {list.map((x) => (
            <div key={x.t} className="border border-border rounded-lg p-3.5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-mono text-sm font-semibold m-0">{x.t}</h3>
                <span className={`inline-flex items-center gap-1 text-[0.7rem] font-semibold px-2 py-0.5 rounded-full ${x.nf === "BCNF" ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}>
                  {x.nf === "BCNF" ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />} {x.nf}
                </span>
              </div>
              <div className="text-xs space-y-1">
                <div><KeyRound size={11} className="inline text-accent" /> <strong>PK:</strong> <span className="font-mono">{x.pk}</span></div>
                {x.ck.length > 0 && <div><strong>Candidate / alternate keys:</strong> <span className="font-mono">{x.ck.join(";  ")}</span></div>}
                {x.fk.length > 0 && <div><Link2 size={11} className="inline text-warn" /> <strong>FK:</strong> <span className="font-mono">{x.fk.join(";  ")}</span></div>}
                <div><strong>FDs:</strong>
                  <ul className="m-0 mt-0.5 pl-4 font-mono text-[0.7rem] text-ink-soft">{x.fd.map((f) => <li key={f}>{f}</li>)}</ul>
                </div>
                {x.note && <div className="text-ink-muted pt-1">{x.note}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
