import { useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import LookupSelect from "../components/LookupSelect";
import { Stethoscope, FileText } from "lucide-react";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";

export default function ClinicalPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [patientId, setPatientId] = useState("");
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [note, setNote] = useState({ patient_id: "", doctor_id: "", note_text: "" });
  const [noteResult, setNoteResult] = useState(null);
  const [noteError, setNoteError] = useState(null);

  async function loadSummary(e) {
    e?.preventDefault(); setSummaryError(null); setSummaryLoading(true);
    try { const res = await apiFetch(`/clinical/patient-summary/${patientId}`, { token: auth.token }); setSummary(res); }
    catch (err) { setSummaryError(err.message); }
    finally { setSummaryLoading(false); }
  }

  async function submitNote(e) {
    e.preventDefault(); setNoteError(null);
    try {
      const res = await apiCall("/clinical/notes", { token: auth.token, params: note });
      setNoteResult(res); toast.success(`Note saved — ID ${res.note_id}`);
      setNote({ ...note, note_text: "" });
    } catch (err) { setNoteError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Clinical workspace" subtitle="Review a patient's medical history and record clinical notes." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><Stethoscope size={18} className="text-accent" /> Patient medical summary</h2>
        </div>
        <form onSubmit={loadSummary} className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <Field label="Patient ID"><input className={inputCls} value={patientId} onChange={(e) => setPatientId(e.target.value)} required /></Field>
          </div>
          <button type="submit" disabled={summaryLoading} className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50">
            {summaryLoading ? "Loading…" : "Load"}
          </button>
        </form>
        {summaryError && <p className="text-urgent">{summaryError}</p>}
        {summary && (
          <div className="mt-4">
            <DataTable rows={summary.results} filename="patient-summary.csv" />
            <SqlPanel sql={summary.sql_executed} />
          </div>
        )}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><FileText size={18} className="text-accent" /> Add clinical note</h2>
        </div>
        <form onSubmit={submitNote}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-2">
            <LookupSelect label="Patient" value={note.patient_id} onChange={(v) => setNote({ ...note, patient_id: v })} lookupPath="/patients/search?last_name=" labelFn={(r) => `${r.patient_id ?? r.id ?? ""} — ${[r.first_name, r.last_name].filter(Boolean).join(" ")}`} required />
            <LookupSelect label="Doctor" value={note.doctor_id} onChange={(v) => setNote({ ...note, doctor_id: v })} lookupPath="/doctors" labelFn={(r) => `${r.doctor_id ?? r.id ?? ""} — Dr. ${r.first_name ?? ""} ${r.last_name ?? ""}`.trim()} required />
          </div>
          <Field label="Note" required>
            <textarea className={inputCls} rows={4} value={note.note_text} onChange={(e) => setNote({ ...note, note_text: e.target.value })} required />
          </Field>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Save note</button>
          {noteError && <p className="text-urgent mt-2">{noteError}</p>}
          {noteResult && <p className="text-ink-muted text-sm mt-3">Saved — note ID <strong>{noteResult.note_id}</strong></p>}
        </form>
      </div>
    </div>
  );
}