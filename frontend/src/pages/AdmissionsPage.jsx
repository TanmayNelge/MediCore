import { useCallback, useMemo, useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import LookupSelect from "../components/LookupSelect";
import { BedDouble, UserPlus, LogOut, RefreshCw } from "lucide-react";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";
const BLANK_ADMIT = { patient_id: "", room_bed_id: "", doctor_id: "", reason: "" };

export default function AdmissionsPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const fetchAdmitted = useCallback((token) => apiFetch("/reports/admitted-patients", { token }), []);
  const fetchBeds = useCallback((token) => apiFetch("/admissions/available-beds", { token }), []);
  const admitted = useApi(fetchAdmitted);
  const beds = useApi(fetchBeds);

  const [admitForm, setAdmitForm] = useState(BLANK_ADMIT);
  const [admitResult, setAdmitResult] = useState(null);
  const [admitError, setAdmitError] = useState(null);
  const [admissionId, setAdmissionId] = useState("");
  const [dischargeResult, setDischargeResult] = useState(null);
  const [dischargeError, setDischargeError] = useState(null);

  const admittedRows = admitted.data?.results || [];
  const bedRows = beds.data?.results || [];

  const admissionOptions = useMemo(() => admittedRows.map((r, i) => {
    const id = r.admission_id ?? r.id ?? r["ADMISSION_ID"];
    const pid = r.patient_id ?? r["PATIENT_ID"];
    const name = [r.first_name, r.last_name].filter(Boolean).join(" ") || r.patient_name || "";
    return { value: String(id ?? i), label: `#${id ?? "?"} — ${name || "Patient " + pid}` };
  }).filter((o) => o.value !== "undefined"), [admittedRows]);

  function updateAdmit(field, value) { setAdmitForm((f) => ({ ...f, [field]: value })); }

  async function admit(e) {
    e.preventDefault(); setAdmitError(null);
    try {
      const res = await apiCall("/admissions/admit", { token: auth.token, params: admitForm });
      setAdmitResult(res); toast.success(`Admitted — admission ID ${res.admission_id}`);
      setAdmitForm(BLANK_ADMIT); admitted.reload(); beds.reload();
    } catch (err) { setAdmitError(err.message); toast.error(err.message); }
  }

  async function discharge(e) {
    e.preventDefault(); setDischargeError(null);
    try {
      const res = await apiCall(`/clinical/discharge/${admissionId}`, { token: auth.token });
      setDischargeResult(res); toast.success(`Discharge complete — status ${res.status}`);
      setAdmissionId(""); admitted.reload(); beds.reload();
    } catch (err) { setDischargeError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Admissions & beds" subtitle="Admit patients, monitor occupancy, and discharge." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><UserPlus size={18} className="text-accent" /> Admit patient</h2>
          <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-ok-soft text-ok">{bedRows.length} bed{bedRows.length !== 1 ? "s" : ""} available</span>
        </div>
        <p className="text-ink-muted text-sm mt-0">Bed status flips to OCCUPIED automatically via a database trigger.</p>
        <form onSubmit={admit}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-3">
            <LookupSelect label="Patient" value={admitForm.patient_id} onChange={(v) => updateAdmit("patient_id", v)} lookupPath="/patients/search?last_name=" labelFn={(r) => `${r.patient_id ?? r.id ?? ""} — ${[r.first_name, r.last_name].filter(Boolean).join(" ")}`} required />
            <LookupSelect label="Admitting doctor" value={admitForm.doctor_id} onChange={(v) => updateAdmit("doctor_id", v)} lookupPath="/doctors" labelFn={(r) => `${r.doctor_id ?? r.id ?? ""} — Dr. ${r.first_name ?? ""} ${r.last_name ?? ""}`.trim()} required />
            <Field label="Bed" required hint={`${bedRows.length} available`}>
              <select className={inputCls} value={admitForm.room_bed_id} onChange={(e) => updateAdmit("room_bed_id", e.target.value)} required>
                <option value="">Select an available bed…</option>
                {bedRows.map((b) => (<option key={b.room_bed_id} value={b.room_bed_id}>Room {b.room_no} / Bed {b.bed_no} — {b.room_type} (₹{b.daily_rate}/day)</option>))}
              </select>
            </Field>
          </div>
          <Field label="Admission reason" required><input className={inputCls} value={admitForm.reason} onChange={(e) => updateAdmit("reason", e.target.value)} required /></Field>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Admit patient</button>
          {admitError && <p className="text-urgent mt-2">{admitError}</p>}
          {admitResult && (
            <div className="mt-3">
              <p className="text-ink-muted text-sm">Admitted — admission ID <strong>{admitResult.admission_id}</strong></p>
              <SqlPanel sql={admitResult.sql_executed} />
            </div>
          )}
        </form>
        {beds.data && <SqlPanel sql={beds.data.sql_executed} />}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><BedDouble size={18} className="text-accent" /> Currently admitted patients</h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={admitted.reload} disabled={admitted.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {admitted.loading && !admitted.data && <div className="h-24 bg-surface-3 rounded animate-pulse" />}
        {admitted.error && <p className="text-urgent">{admitted.error}</p>}
        {admitted.data && (
          <>
            <DataTable rows={admittedRows} filename="admitted.csv" emptyMessage="No patients currently admitted." />
            <SqlPanel sql={admitted.data.sql_executed} />
          </>
        )}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><LogOut size={18} className="text-accent" /> Discharge patient</h2>
        </div>
        <p className="text-ink-muted text-sm mt-0">Bed status flips to AVAILABLE automatically via a database trigger.</p>
        <form onSubmit={discharge} className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[220px]">
            <Field label="Admission">
              {admissionOptions.length > 0 ? (
                <select className={inputCls} value={admissionId} onChange={(e) => setAdmissionId(e.target.value)} required>
                  <option value="">Select an admission…</option>
                  {admissionOptions.map((o) => (<option key={o.value} value={o.value}>{o.label}</option>))}
                </select>
              ) : (
                <input className={inputCls} value={admissionId} onChange={(e) => setAdmissionId(e.target.value)} placeholder="Enter admission ID" required />
              )}
            </Field>
          </div>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-urgent hover:bg-[#9a3a25] text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Discharge</button>
        </form>
        {dischargeError && <p className="text-urgent">{dischargeError}</p>}
        {dischargeResult && (
          <div className="mt-3">
            <p className="text-ink-muted text-sm">Status: <strong>{dischargeResult.status}</strong></p>
            <SqlPanel sql={dischargeResult.sql_executed} />
          </div>
        )}
      </div>
    </div>
  );
}