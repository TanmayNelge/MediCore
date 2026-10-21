import { useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { apiFetch } from "../api";
import { useApi } from "../lib/useApi";
import { fmtMoney, dash } from "../lib/format";
import SqlPanel from "../components/SqlPanel";
import EcgLine from "../components/EcgLine";
import {
  Users, CalendarDays, ListOrdered, BedDouble, FlaskConical, Receipt,
  RefreshCw, ArrowRight, Activity,
} from "lucide-react";

const CARDS = [
  { key: "total_patients", label: "Total patients", icon: Users, tone: "" },
  { key: "todays_appointments", label: "Today's appointments", icon: CalendarDays, tone: "" },
  { key: "current_queue", label: "Currently waiting", icon: ListOrdered, tone: "warn" },
  { key: "available_beds", label: "Available beds", icon: BedDouble, tone: "ok" },
  { key: "pending_labs", label: "Pending lab reports", icon: FlaskConical, tone: "warn" },
  { key: "revenue_today", label: "Revenue today", icon: Receipt, tone: "", money: true },
];

export default function DashboardPage() {
  const { auth } = useAuth();
  const fetchDashboard = useCallback((token) => apiFetch("/reports/dashboard", { token }), []);
  const { data, loading, error, reload } = useApi(fetchDashboard);
  const kpis = data?.results?.[0];

  return (
    <div>
      <div className="relative rounded-2xl px-6 sm:px-9 py-8 mb-7 text-[#eaf4f0] overflow-hidden shadow-lg bg-hero animate-rise">
        <div className="absolute inset-0 bg-dots" />
        <div className="absolute -right-10 -top-16 h-64 w-64 rounded-full bg-accent-bright/20 blur-3xl" />
        <svg className="absolute right-6 -bottom-10 h-56 w-56 text-white/[0.05]" viewBox="0 0 100 100" fill="currentColor" aria-hidden="true">
          <path d="M38 6h24v32h32v24H62v32H38V62H6V38h32z" />
        </svg>
        <EcgLine className="absolute left-0 right-0 bottom-0 h-24 w-full" opacity={0.55} />
        <div className="relative z-10 flex justify-between items-end gap-6 flex-wrap">
          <div>
            <div className="text-[0.74rem] uppercase tracking-[0.14em] text-accent-bright font-semibold mb-2">
              Clinical Operations
            </div>
            <h1 className="text-white text-3xl font-display font-semibold m-0 mb-1.5">Dashboard</h1>
            <p className="text-[#b8d4cc] text-sm m-0">
              Signed in as <strong className="text-white">{auth?.username}</strong> · <span className="capitalize">{auth?.role}</span>
            </p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="inline-flex items-center gap-2 glass px-3 py-1.5 rounded-full text-xs text-[#d5e8e3]">
              <span className="w-2 h-2 rounded-full bg-[#4ee2b3] shadow-[0_0_0_3px_rgba(78,226,179,0.2)] animate-pulse" />
              Oracle connected
            </span>
            <button className="glass text-white rounded-lg px-3.5 py-2 text-sm inline-flex items-center gap-1.5 hover:bg-white/20 transition-colors disabled:opacity-60" onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {error && <p className="text-urgent mb-4">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-7">
        {CARDS.map(({ key, label, icon: Icon, tone, money }) => (
          <div
            key={key}
            className={`relative bg-surface border border-border rounded-xl p-5 shadow-sm overflow-hidden hover:shadow-md hover:-translate-y-0.5 transition-all border-t-[3px] ${
              tone === "warn" ? "border-t-warn" : tone === "ok" ? "border-t-ok" : "border-t-accent"
            }`}
          >
            <div className="flex justify-between items-start mb-3">
              <span className="text-sm text-ink-muted font-medium">{label}</span>
              <span className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                tone === "warn" ? "bg-warn-soft text-warn" : tone === "ok" ? "bg-ok-soft text-ok" : "bg-accent-soft text-accent-strong"
              }`}>
                <Icon size={18} />
              </span>
            </div>
            <div className="font-display text-[2rem] font-semibold leading-none tabular-nums tracking-tight">
              {loading || !kpis
                ? <span className="inline-block w-16 h-8 bg-surface-3 rounded animate-pulse" />
                : money ? fmtMoney(kpis[key]) : dash(kpis[key])}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-surface border border-border rounded-xl p-5 mb-6 shadow-sm">
        <div className="flex justify-between items-center mb-4 pb-3 border-b border-border">
          <h2 className="text-lg font-display m-0 flex items-center gap-2">
            <Activity size={18} className="text-accent" /> Quick actions
          </h2>
        </div>
        <div className="flex flex-wrap gap-3">
          {[
            ["/patients", "Register patient"],
            ["/appointments", "Book appointment"],
            ["/admissions", "Admit patient"],
            ["/queue", "Call next in queue"],
          ].map(([to, label]) => (
            <Link key={to} to={to} className="inline-flex items-center gap-1.5 bg-surface-2 border border-border rounded-md px-3.5 py-2 text-sm text-ink-soft hover:bg-accent-soft hover:border-accent hover:text-accent-strong transition-colors">
              {label} <ArrowRight size={14} />
            </Link>
          ))}
        </div>
      </div>

      {data && <SqlPanel sql={data.sql_executed} />}
    </div>
  );
}