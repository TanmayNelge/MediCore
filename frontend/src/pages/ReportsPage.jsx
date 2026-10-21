import { useState, useCallback } from "react";
import { apiFetch } from "../api";
import { useApi } from "../lib/useApi";
import SqlPanel from "../components/SqlPanel";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import { BarChart3, RefreshCw } from "lucide-react";

const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const REPORTS = [
  { key: "doctor-workload", label: "Doctor workload", path: "/reports/doctor-workload" },
  { key: "admitted", label: "Admitted patients", path: "/reports/admitted-patients" },
];

export default function ReportsPage() {
  const [active, setActive] = useState(REPORTS[0]);
  const fetcher = useCallback((token) => apiFetch(active.path, { token }), [active.path]);
  const report = useApi(fetcher);

  return (
    <div>
      <PageHeader title="Reports" subtitle="Operational reports built from Oracle views." />

      <div className={panelCls}>
        <div className="flex items-center gap-2 flex-wrap mb-4">
          {REPORTS.map((r) => (
            <button
              key={r.key}
              onClick={() => setActive(r)}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm transition-colors ${
                active.key === r.key
                  ? "bg-accent hover:bg-accent-strong text-white"
                  : "bg-surface border border-border-strong text-accent-strong hover:bg-accent-soft"
              }`}
            >
              <BarChart3 size={14} /> {r.label}
            </button>
          ))}
          <div className="flex-1" />
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={report.reload} disabled={report.loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {report.loading && !report.data && <div className="h-28 bg-surface-3 rounded animate-pulse" />}
        {report.error && <p className="text-urgent">{report.error}</p>}
        {report.data && (
          <>
            <DataTable rows={report.data.results} filename={`${active.key}.csv`} emptyMessage="No data for this report yet." />
            <SqlPanel sql={report.data.sql_executed} />
          </>
        )}
      </div>
    </div>
  );
}