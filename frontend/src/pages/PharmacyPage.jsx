import { useCallback, useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import LookupSelect from "../components/LookupSelect";
import { Pill, Package, RefreshCw } from "lucide-react";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";
const BLANK_RX = { patient_id: "", doctor_id: "", appointment_id: "", medicine_id: "", dosage: "", duration_days: "", quantity: "" };

export default function PharmacyPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [rx, setRx] = useState(BLANK_RX);
  const [rxResult, setRxResult] = useState(null);
  const [error, setError] = useState(null);
  const fetchInventory = useCallback((token) => apiFetch("/pharmacy/inventory", { token }), []);
  const inventory = useApi(fetchInventory);

  async function submitRx(e) {
    e.preventDefault(); setError(null);
    try {
      const res = await apiCall("/pharmacy/prescriptions", { token: auth.token, params: rx });
      setRxResult(res); toast.success(`Prescription saved — ID ${res.prescription_id}`);
      setRx(BLANK_RX); inventory.reload();
    } catch (err) { setError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Pharmacy" subtitle="Record prescriptions and monitor medicine inventory." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><Pill size={18} className="text-accent" /> Add prescription</h2>
        </div>
        <form onSubmit={submitRx}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            <LookupSelect label="Patient" value={rx.patient_id} onChange={(v) => setRx({ ...rx, patient_id: v })} lookupPath="/patients/search?last_name=" labelFn={(r) => `${r.patient_id ?? r.id ?? ""} — ${[r.first_name, r.last_name].filter(Boolean).join(" ")}`} required />
            <LookupSelect label="Doctor" value={rx.doctor_id} onChange={(v) => setRx({ ...rx, doctor_id: v })} lookupPath="/doctors" labelFn={(r) => `${r.doctor_id ?? r.id ?? ""} — Dr. ${r.first_name ?? ""} ${r.last_name ?? ""}`.trim()} required />
            <Field label="Appointment ID"><input className={inputCls} value={rx.appointment_id} onChange={(e) => setRx({ ...rx, appointment_id: e.target.value })} /></Field>
            <LookupSelect label="Medicine" value={rx.medicine_id} onChange={(v) => setRx({ ...rx, medicine_id: v })} lookupPath="/pharmacy/medicines" labelFn={(r) => `${r.medicine_id ?? r.id ?? ""} — ${r.name ?? r.medicine_name ?? ""}`} required />
            <Field label="Dosage" required><input className={inputCls} value={rx.dosage} onChange={(e) => setRx({ ...rx, dosage: e.target.value })} placeholder="e.g. 500mg twice daily" /></Field>
            <Field label="Duration (days)" required><input className={inputCls} type="number" min={1} value={rx.duration_days} onChange={(e) => setRx({ ...rx, duration_days: e.target.value })} required /></Field>
            <Field label="Quantity" required><input className={inputCls} type="number" min={1} value={rx.quantity} onChange={(e) => setRx({ ...rx, quantity: e.target.value })} required /></Field>
          </div>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Save prescription</button>
          {error && <p className="text-urgent mt-2">{error}</p>}
          {rxResult && <p className="text-ink-muted text-sm mt-3">Saved — prescription ID <strong>{rxResult.prescription_id}</strong></p>}
        </form>
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><Package size={18} className="text-accent" /> Medicine inventory</h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={inventory.reload} disabled={inventory.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {inventory.loading && !inventory.data && <div className="h-24 bg-surface-3 rounded animate-pulse" />}
        {inventory.error && <p className="text-urgent">{inventory.error}</p>}
        {inventory.data && (
          <>
            <DataTable rows={inventory.data.results} filename="inventory.csv" emptyMessage="No medicines in inventory." />
            <SqlPanel sql={inventory.data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}