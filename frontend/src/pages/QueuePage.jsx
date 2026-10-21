import { useCallback, useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import { ListOrdered, AlertTriangle, RefreshCw, UserCheck } from "lucide-react";

const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";
const QUEUE_TYPES = ["OPD", "EMERGENCY", "LAB", "PHARMACY"];

export default function QueuePage() {
  const { auth } = useAuth();
  const toast = useToast();
  const [nextResult, setNextResult] = useState(null);
  const [error, setError] = useState(null);
  const [calling, setCalling] = useState(null);
  const fetchWait = useCallback((token) => apiFetch("/queue/wait-estimate", { token }), []);
  const fetchEmergency = useCallback((token) => apiFetch("/queue/emergency-list", { token }), []);
  const waitEstimate = useApi(fetchWait);
  const emergency = useApi(fetchEmergency);

  async function callNext(queueType) {
    setError(null); setCalling(queueType);
    try {
      const res = await apiCall("/queue/next", { token: auth.token, params: { queue_type: queueType } });
      setNextResult({ ...res, queueType });
      if (res.patient_id) toast.success(`Called next from ${queueType} — patient ${res.patient_id}`);
      else toast.push(res.message || `${queueType} queue is empty`, "success");
      waitEstimate.reload(); emergency.reload();
    } catch (err) { setError(err.message); toast.error(err.message); }
    finally { setCalling(null); }
  }

  return (
    <div>
      <PageHeader title="Queue console" subtitle="Call the next patient in each queue and monitor wait times." />

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><UserCheck size={18} className="text-accent" /> Call next patient</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {QUEUE_TYPES.map((t) => (
            <button
              key={t}
              className={`justify-center px-4 py-3 rounded-md text-sm font-medium transition-colors disabled:opacity-50 ${
                t === "EMERGENCY"
                  ? "bg-urgent hover:bg-[#9a3a25] text-white"
                  : "bg-surface border border-border-strong text-accent-strong hover:bg-accent-soft"
              }`}
              onClick={() => callNext(t)}
              disabled={calling !== null}
            >
              {calling === t ? "Calling…" : t}
            </button>
          ))}
        </div>
        {nextResult && (
          <div className="mt-4 bg-surface-2 border border-border rounded-lg p-4">
            <div className="flex justify-between items-center gap-3 flex-wrap">
              <span className="text-sm">{nextResult.message}</span>
              {nextResult.patient_id && <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-ok-soft text-ok">Patient {nextResult.patient_id} · queue {nextResult.queue_id}</span>}
              <button className="ml-auto p-1 rounded text-ink-muted hover:bg-surface-3" onClick={() => setNextResult(null)}>×</button>
            </div>
            <SqlPanel sql={nextResult.sql_executed} />
          </div>
        )}
        {error && <p className="text-urgent mt-2">{error}</p>}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><ListOrdered size={18} className="text-accent" /> OPD wait estimate <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-accent-soft text-accent-strong">today</span></h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={waitEstimate.reload} disabled={waitEstimate.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {waitEstimate.loading && !waitEstimate.data && <div className="h-20 bg-surface-3 rounded animate-pulse" />}
        {waitEstimate.error && <p className="text-urgent">{waitEstimate.error}</p>}
        {waitEstimate.data && (
          <>
            <DataTable rows={waitEstimate.data.results} filename="wait-estimate.csv" emptyMessage="No one waiting in OPD." />
            <SqlPanel sql={waitEstimate.data.sql_executed} />
          </>
        )}
      </div>

      <div className={panelCls}>
        <div className={panelHeadCls}>
          <h2 className="text-lg font-display m-0 flex items-center gap-2"><AlertTriangle size={18} className="text-urgent" /> Emergency queue <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-urgent-soft text-urgent">priority</span></h2>
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={emergency.reload} disabled={emergency.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {emergency.loading && !emergency.data && <div className="h-20 bg-surface-3 rounded animate-pulse" />}
        {emergency.error && <p className="text-urgent">{emergency.error}</p>}
        {emergency.data && (
          <>
            <DataTable rows={emergency.data.results} filename="emergency-queue.csv" emptyMessage="Emergency queue is clear." />
            <SqlPanel sql={emergency.data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}