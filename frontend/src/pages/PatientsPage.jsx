import { useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import { UserPlus, Search, ChevronDown, Loader2 } from "lucide-react";

const BLANK_PATIENT = {
  first_name: "", last_name: "", dob: "", gender: "M", blood_group: "",
  phone: "", email: "", address: "", emergency_contact_name: "", emergency_contact_phone: "",
};

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";

export default function PatientsPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState(BLANK_PATIENT);
  const [registerResult, setRegisterResult] = useState(null);
  const [registerError, setRegisterError] = useState(null);
  const [registering, setRegistering] = useState(false);
  const [regOpen, setRegOpen] = useState(true);
  const [lastName, setLastName] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  function updateForm(field, value) { setForm((f) => ({ ...f, [field]: value })); }

  async function register(e) {
    e.preventDefault(); setRegisterError(null); setRegistering(true);
    try {
      const params = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ""));
      const res = await apiCall("/patients", { token: auth.token, params });
      setRegisterResult(res); setForm(BLANK_PATIENT);
      toast.success(`Patient registered — ID ${res.patient_id}`);
    } catch (err) { setRegisterError(err.message); toast.error(err.message); }
    finally { setRegistering(false); }
  }

  async function search(e) {
    e?.preventDefault(); setLoading(true); setError(null);
    try {
      const res = await apiFetch("/patients/search", { token: auth.token, params: { last_name: lastName } });
      setData(res);
    } catch (err) { setError(err.message); toast.error(err.message); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="Patients" subtitle="Register new patients and search existing records." />

      <div className={panelCls}>
        <div className={`${panelHeadCls} cursor-pointer`} onClick={() => setRegOpen((o) => !o)}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2">
            <UserPlus size={18} className="text-accent" /> Register new patient
          </h2>
          <ChevronDown size={18} className="text-ink-muted transition-transform" style={{ transform: regOpen ? "rotate(180deg)" : "none" }} />
        </div>

        {regOpen && (
          <form onSubmit={register}>
            <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="First name" required><input className={inputCls} value={form.first_name} onChange={(e) => updateForm("first_name", e.target.value)} required /></Field>
              <Field label="Last name" required><input className={inputCls} value={form.last_name} onChange={(e) => updateForm("last_name", e.target.value)} required /></Field>
              <Field label="Date of birth" required><input className={inputCls} type="date" value={form.dob} onChange={(e) => updateForm("dob", e.target.value)} required /></Field>
              <Field label="Gender">
                <select className={inputCls} value={form.gender} onChange={(e) => updateForm("gender", e.target.value)}>
                  <option value="M">Male</option><option value="F">Female</option><option value="O">Other</option>
                </select>
              </Field>
              <Field label="Blood group" hint="e.g. O+"><input className={inputCls} value={form.blood_group} onChange={(e) => updateForm("blood_group", e.target.value)} placeholder="O+" /></Field>
              <Field label="Phone" required><input className={inputCls} value={form.phone} onChange={(e) => updateForm("phone", e.target.value)} required /></Field>
              <Field label="Email"><input className={inputCls} type="email" value={form.email} onChange={(e) => updateForm("email", e.target.value)} /></Field>
              <Field label="Address"><input className={inputCls} value={form.address} onChange={(e) => updateForm("address", e.target.value)} /></Field>
              <Field label="Emergency contact name"><input className={inputCls} value={form.emergency_contact_name} onChange={(e) => updateForm("emergency_contact_name", e.target.value)} /></Field>
              <Field label="Emergency contact phone"><input className={inputCls} value={form.emergency_contact_phone} onChange={(e) => updateForm("emergency_contact_phone", e.target.value)} /></Field>
            </div>
            <button type="submit" disabled={registering} className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50">
              {registering ? <><Loader2 size={15} className="animate-spin" /> Registering…</> : "Register patient"}
            </button>
            {registerError && <p className="text-urgent mt-2">{registerError}</p>}
            {registerResult && (
              <div className="mt-3">
                <p className="text-ink-muted text-sm">Registered — patient ID <strong>{registerResult.patient_id}</strong></p>
                <SqlPanel sql={registerResult.sql_executed} />
              </div>
            )}
          </form>
        )}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}><h2 className="text-lg font-display m-0">Search patients</h2></div>
        <p className="text-ink-muted text-sm mt-0">Search by last name (matches from the start of the name).</p>
        <form onSubmit={search} className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <Field label="Last name" htmlFor="ln">
              <input id="ln" className={inputCls} value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="e.g. Shah" />
            </Field>
          </div>
          <button type="submit" disabled={loading} className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50">
            <Search size={15} /> {loading ? "Searching…" : "Search"}
          </button>
        </form>
        {error && <p className="text-urgent">{error}</p>}
        {data && (
          <>
            <DataTable rows={data.results} filename="patients.csv" emptyMessage="No patients matched that name." />
            <SqlPanel sql={data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}