import { useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Field from "../components/Field";
import { Receipt, CreditCard } from "lucide-react";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";
const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";
const MODES = ["CASH", "CARD", "UPI", "INSURANCE", "NET_BANKING"];

export default function BillingPage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [patientId, setPatientId] = useState("");
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [payment, setPayment] = useState({ bill_id: "", amount_paid: "", payment_mode: "CASH" });
  const [paymentResult, setPaymentResult] = useState(null);
  const [paymentError, setPaymentError] = useState(null);

  async function loadSummary(e) {
    e?.preventDefault(); setSummaryError(null); setSummaryLoading(true);
    try { const res = await apiFetch(`/billing/summary/${patientId}`, { token: auth.token }); setSummary(res); }
    catch (err) { setSummaryError(err.message); }
    finally { setSummaryLoading(false); }
  }

  async function submitPayment(e) {
    e.preventDefault(); setPaymentError(null);
    try {
      const res = await apiCall("/billing/payments", { token: auth.token, params: payment });
      setPaymentResult(res); toast.success(`Payment recorded — ID ${res.payment_id}`);
      setPayment({ bill_id: "", amount_paid: "", payment_mode: "CASH" });
      if (patientId) loadSummary();
    } catch (err) { setPaymentError(err.message); toast.error(err.message); }
  }

  return (
    <div>
      <PageHeader title="Billing & payments" subtitle="Review a patient's bills and record payments." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><Receipt size={18} className="text-accent" /> Billing summary</h2>
        </div>
        <form onSubmit={loadSummary} className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <Field label="Patient ID"><input className={inputCls} value={patientId} onChange={(e) => setPatientId(e.target.value)} required /></Field>
          </div>
          <button type="submit" disabled={summaryLoading} className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50">{summaryLoading ? "Loading…" : "Load"}</button>
        </form>
        {summaryError && <p className="text-urgent">{summaryError}</p>}
        {summary && (
          <div className="mt-4">
            <DataTable rows={summary.results} filename="billing-summary.csv" />
            <SqlPanel sql={summary.sql_executed} />
          </div>
        )}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><CreditCard size={18} className="text-accent" /> Record payment</h2>
        </div>
        <form onSubmit={submitPayment}>
          <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-3">
            <Field label="Bill ID" required><input className={inputCls} value={payment.bill_id} onChange={(e) => setPayment({ ...payment, bill_id: e.target.value })} required /></Field>
            <Field label="Amount paid" required><input className={inputCls} type="number" min={0} step="0.01" value={payment.amount_paid} onChange={(e) => setPayment({ ...payment, amount_paid: e.target.value })} required /></Field>
            <Field label="Payment mode">
              <select className={inputCls} value={payment.payment_mode} onChange={(e) => setPayment({ ...payment, payment_mode: e.target.value })}>
                {MODES.map((m) => (<option key={m} value={m}>{m.replace("_", " ")}</option>))}
              </select>
            </Field>
          </div>
          <button type="submit" className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-4 py-2 text-sm font-medium transition-colors">Record payment</button>
          {paymentError && <p className="text-urgent mt-2">{paymentError}</p>}
          {paymentResult && <p className="text-ink-muted text-sm mt-3">Recorded — payment ID <strong>{paymentResult.payment_id}</strong></p>}
        </form>
      </div>
    </div>
  );
}