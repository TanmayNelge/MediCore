import { useCallback, useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import LookupSelect from "../components/LookupSelect";
import { FlaskConical, ClipboardList, RefreshCw } from "lucide-react";

const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";

export default function LabPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [order, setOrder] = useState({ patient_id: "", doctor_id: "", lab_test_id: "" });
  const [orderResult, setOrderResult] = useState(null);
  const [error, setError] = useState(null);
  const fetchPending = useCallback((token) => apiFetch("/lab/pending", { token }), []);
  const pending = useApi(fetchPending);

  async function submitOrder(e) {
    e.preventDefault(); setError(null);
    try {
      const res = await apiCall("/lab/orders", { token: auth.token, params: order });
      setOrderResult(res); toast.success(`Lab order registered — ID ${res.lab_order_id}`);
      setOrder({ patient_id: "", doctor_id: "", lab_test_id: "" }); pending.reload();
    } catch (err) { setError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Lab" subtitle="Register lab orders and review pending lab reports." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><FlaskConical size={18} className="text-accent" /> Register lab order</h2>
        </div>
        <form onSubmit={submitOrder}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-3">
            <LookupSelect label="Patient" value={order.patient_id} onChange={(v) => setOrder({ ...order, patient_id: v })} lookupPath="/patients/search?last_name=" labelFn={(r) => `${r.patient_id ?? r.id ?? ""} — ${[r.first_name, r.last_name].filter(Boolean).join(" ")}`} required />
            <LookupSelect label="Doctor" value={order.doctor_id} onChange={(v) => setOrder({ ...order, doctor_id: v })} lookupPath="/doctors" labelFn={(r) => `${r.doctor_id ?? r.id ?? ""} — Dr. ${r.first_name ?? ""} ${r.last_name ?? ""}`.trim()} required />
            <LookupSelect label="Lab test" value={order.lab_test_id} onChange={(v) => setOrder({ ...order, lab_test_id: v })} lookupPath="/lab/tests" labelFn={(r) => `${r.lab_test_id ?? r.id ?? ""} — ${r.test_name ?? r.name ?? ""}`} required />
          </div>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Register order</button>
          {error && <p className="text-urgent mt-2">{error}</p>}
          {orderResult && <p className="text-ink-muted text-sm mt-3">Registered — lab order ID <strong>{orderResult.lab_order_id}</strong></p>}
        </form>
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><ClipboardList size={18} className="text-accent" /> Pending lab reports</h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={pending.reload} disabled={pending.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {pending.loading && !pending.data && <div className="h-24 bg-surface-3 rounded animate-pulse" />}
        {pending.error && <p className="text-urgent">{pending.error}</p>}
        {pending.data && (
          <>
            <DataTable rows={pending.data.results} filename="pending-labs.csv" emptyMessage="Nothing pending — lab is up to date." />
            <SqlPanel sql={pending.data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}