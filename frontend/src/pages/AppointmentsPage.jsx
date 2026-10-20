import { useState, useCallback } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import { todayISO } from "../lib/format";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import LookupSelect from "../components/LookupSelect";
import { CalendarPlus, RefreshCw } from "lucide-react";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";

export default function AppointmentsPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ patient_id: "", doctor_id: "", appt_date: todayISO(), appt_time: "", reason: "" });
  const [bookResult, setBookResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchSchedule = useCallback((token) => apiFetch("/appointments/schedule", { token }), []);
  const schedule = useApi(fetchSchedule);

  function update(field, value) { setForm((f) => ({ ...f, [field]: value })); }

  async function book(e) {
    e.preventDefault(); setError(null);
    try {
      const res = await apiCall("/appointments/book", { token: auth.token, params: form });
      setBookResult(res);
      toast.success(`Appointment booked — ID ${res.appointment_id}`);
      schedule.reload();
    } catch (err) { setError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Appointments" subtitle="Book a new appointment and review the doctor schedule." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><CalendarPlus size={18} className="text-accent" /> Book an appointment</h2>
        </div>
        <form onSubmit={book}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <LookupSelect label="Patient" value={form.patient_id} onChange={(v) => update("patient_id", v)} lookupPath="/patients/search?last_name=" labelFn={(r) => `${r.patient_id ?? r.id ?? ""} — ${[r.first_name, r.last_name].filter(Boolean).join(" ") || r.name || ""}`} required />
            <LookupSelect label="Doctor" value={form.doctor_id} onChange={(v) => update("doctor_id", v)} lookupPath="/doctors" labelFn={(r) => `${r.doctor_id ?? r.id ?? ""} — Dr. ${r.first_name ?? ""} ${r.last_name ?? ""}`.trim()} required />
            <Field label="Date" required><input className={inputCls} type="date" value={form.appt_date} onChange={(e) => update("appt_date", e.target.value)} required /></Field>
            <Field label="Time" required><input className={inputCls} type="time" value={form.appt_time} onChange={(e) => update("appt_time", e.target.value)} required /></Field>
          </div>
          <Field label="Reason"><input className={inputCls} value={form.reason} onChange={(e) => update("reason", e.target.value)} placeholder="Reason for visit" /></Field>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Book appointment</button>
          {error && <p className="text-urgent mt-2">{error}</p>}
          {bookResult && <p className="text-ink-muted text-sm mt-3">Booked — appointment ID <strong>{bookResult.appointment_id}</strong></p>}
        </form>
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0">Doctor schedule</h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={schedule.reload} disabled={schedule.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {schedule.loading && !schedule.data && <div className="h-24 bg-surface-3 rounded animate-pulse" />}
        {schedule.error && <p className="text-urgent">{schedule.error}</p>}
        {schedule.data && (
          <>
            <DataTable rows={schedule.data.results} filename="schedule.csv" emptyMessage="No scheduled appointments." />
            <SqlPanel sql={schedule.data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}