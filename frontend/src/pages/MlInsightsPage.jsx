import { useState, useCallback, useEffect } from "react";
import { apiFetch } from "../api";
import { useApi } from "../lib/useApi";
import SqlPanel from "../components/SqlPanel";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { Brain, AlertCircle, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck, Cpu, Filter, Info, PhoneCall, Calendar } from "lucide-react";

const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";
const panelHeadCls = "flex justify-between items-center mb-4 pb-3 border-b border-border";

export default function MlInsightsPage() {
  const fetcher = useCallback((token) => apiFetch("/ml-insights/predictions", { token }), []);
  const { data, loading, error, reload } = useApi(fetcher);

  const [modelSummary, setModelSummary] = useState(null);
  const [filter, setFilter] = useState("ALL"); // ALL | HIGH_RISK | LOW_RISK

  useEffect(() => {
    apiFetch("/ml-insights/model-summary")
      .then((res) => setModelSummary(res))
      .catch(() => {});
  }, []);

  const results = data?.results || [];

  const highRiskCount = results.filter(
    (r) => (r.prediction || "").toUpperCase() === "NO_SHOW" || (Number(r.probability) >= 0.5)
  ).length;

  const lowRiskCount = results.length - highRiskCount;
  const avgProb = results.length
    ? Math.round((results.reduce((acc, r) => acc + (Number(r.probability) || 0), 0) / results.length) * 100)
    : 0;

  const filteredResults = results.filter((r) => {
    const isHigh = (r.prediction || "").toUpperCase() === "NO_SHOW" || Number(r.probability) >= 0.5;
    if (filter === "HIGH_RISK") return isHigh;
    if (filter === "LOW_RISK") return !isHigh;
    return true;
  });

  return (
    <div>
      <PageHeader
        title="AI/ML Clinical Insights"
        subtitle="Predictive appointment no-show risk engine, trained on historical visits and scored offline via Oracle PL/SQL."
        actions={
          <button
            className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50"
            onClick={reload}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Refresh Insights
          </button>
        }
      />

      {/* Decision Support Advisory */}
      <div className="bg-warn-soft border border-[#e6d9b3] rounded-xl p-4 mb-5 flex gap-3 items-start">
        <AlertCircle size={20} className="text-warn shrink-0 mt-0.5" />
        <div className="text-sm">
          <strong className="text-warn-strong">Clinical Decision-Support Estimate:</strong>{" "}
          <span className="text-ink-muted">
            Probability scores represent historical behavioral likelihood and are not medical diagnoses. Read-only queries against{" "}
            <code className="text-xs bg-surface px-1.5 py-0.5 rounded border border-border">ML_PREDICTION</code> ensure offline ML batch safety.
          </span>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <div className="bg-surface border border-border rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-ink-muted font-medium uppercase tracking-wider">Upcoming Scored</div>
            <div className="text-2xl font-bold font-display mt-1 text-ink">{results.length}</div>
            <div className="text-xs text-ink-muted mt-0.5">Appointments evaluated</div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-accent-soft flex items-center justify-center text-accent">
            <Calendar size={20} />
          </div>
        </div>

        <div className="bg-surface border border-border rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-ink-muted font-medium uppercase tracking-wider">High Risk No-Shows</div>
            <div className="text-2xl font-bold font-display mt-1 text-urgent">{highRiskCount}</div>
            <div className="text-xs text-ink-muted mt-0.5">Prompt confirmation advised</div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-urgent-soft flex items-center justify-center text-urgent">
            <AlertTriangle size={20} />
          </div>
        </div>

        <div className="bg-surface border border-border rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-ink-muted font-medium uppercase tracking-wider">Avg No-Show Risk</div>
            <div className="text-2xl font-bold font-display mt-1 text-ink">{avgProb}%</div>
            <div className="text-xs text-ink-muted mt-0.5">{lowRiskCount} likely to attend</div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-ok-soft flex items-center justify-center text-ok">
            <ShieldCheck size={20} />
          </div>
        </div>

        <div className="bg-surface border border-border rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs text-ink-muted font-medium uppercase tracking-wider">Active ML Model</div>
            <div className="text-base font-semibold font-display mt-1 text-accent capitalize">
              {modelSummary?.available ? modelSummary.model_name.replace("_", " ") : "Logistic Reg."}
            </div>
            <div className="text-xs text-ink-muted mt-0.5">
              Recall: {modelSummary?.metrics?.recall != null ? `${Math.round(modelSummary.metrics.recall * 100)}%` : "Balanced"}
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-surface-3 flex items-center justify-center text-accent-strong">
            <Cpu size={20} />
          </div>
        </div>
      </div>

      {/* Main Predictions Section */}
      <div className={panelCls}>
        <div className={panelHeadCls}>
          <div>
            <h2 className="text-lg font-display m-0 flex items-center gap-2">
              <Brain size={18} className="text-accent" /> Upcoming No-Show Risk Predictions
            </h2>
            <p className="text-xs text-ink-muted mt-1 m-0">
              Ranked by no-show probability. Staff can proactively contact high-risk patients to protect doctor capacity.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-surface-2 p-1 rounded-lg border border-border text-xs">
            <button
              onClick={() => setFilter("ALL")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${filter === "ALL" ? "bg-surface text-ink shadow-sm" : "text-ink-muted hover:text-ink"}`}
            >
              All ({results.length})
            </button>
            <button
              onClick={() => setFilter("HIGH_RISK")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${filter === "HIGH_RISK" ? "bg-urgent text-white shadow-sm" : "text-ink-muted hover:text-ink"}`}
            >
              High Risk ({highRiskCount})
            </button>
            <button
              onClick={() => setFilter("LOW_RISK")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${filter === "LOW_RISK" ? "bg-ok text-white shadow-sm" : "text-ink-muted hover:text-ink"}`}
            >
              Low Risk ({lowRiskCount})
            </button>
          </div>
        </div>

        {loading && !data && <div className="h-40 bg-surface-3 rounded-lg animate-pulse" />}
        {error && <p className="text-urgent">{error}</p>}

        {data && (
          <>
            {filteredResults.length === 0 ? (
              <div className="text-center py-10 text-ink-muted text-sm">
                No predictions matching current filter.
                {results.length === 0 && (
                  <p className="mt-2 text-xs">
                    Run <code className="bg-surface-3 px-1.5 py-0.5 rounded">python ml/run_pipeline.py</code> or{" "}
                    <code className="bg-surface-3 px-1.5 py-0.5 rounded">.\4_run_ml.ps1</code> to score upcoming appointments.
                  </p>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-border text-xs font-semibold uppercase text-ink-muted tracking-wider">
                      <th className="py-2.5 px-3">Patient</th>
                      <th className="py-2.5 px-3">Appointment</th>
                      <th className="py-2.5 px-3">Doctor / Dept</th>
                      <th className="py-2.5 px-3">Prediction</th>
                      <th className="py-2.5 px-3">Probability</th>
                      <th className="py-2.5 px-3">Staff Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredResults.map((row, idx) => {
                      const prob = Number(row.probability) || 0;
                      const isHigh = (row.prediction || "").toUpperCase() === "NO_SHOW" || prob >= 0.5;
                      const percent = Math.round(prob * 100);

                      return (
                        <tr key={idx} className="hover:bg-surface-2 transition-colors">
                          <td className="py-3 px-3 font-medium text-ink">
                            {row.patient || `Patient #${row.patient_id}`}
                          </td>
                          <td className="py-3 px-3 text-ink-muted">
                            <div>{row.appt_date}</div>
                            <div className="text-xs font-mono text-ink-muted">{row.appt_time}</div>
                          </td>
                          <td className="py-3 px-3 text-ink-muted">
                            <div>{row.doctor_name || `Dr. #${row.doctor_id || "—"}`}</div>
                            {row.department_name && <div className="text-xs text-ink-muted">{row.department_name}</div>}
                          </td>
                          <td className="py-3 px-3">
                            <StatusBadge status={row.prediction || (isHigh ? "NO_SHOW" : "ATTENDED")} />
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <div className="w-20 bg-surface-3 h-2 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${percent >= 50 ? "bg-urgent" : percent >= 30 ? "bg-warn" : "bg-ok"}`}
                                  style={{ width: `${percent}%` }}
                                />
                              </div>
                              <span className="text-xs font-mono font-medium text-ink">{percent}%</span>
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            {isHigh ? (
                              <span className="inline-flex items-center gap-1 text-xs text-urgent font-medium bg-urgent-soft px-2 py-0.5 rounded">
                                <PhoneCall size={12} /> Call to Confirm
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs text-ok font-medium bg-ok-soft px-2 py-0.5 rounded">
                                <CheckCircle2 size={12} /> SMS Reminder
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-4">
              <SqlPanel sql={data.sql_executed} />
            </div>
          </>
        )}
      </div>

      {/* Model Technical Architecture & How It Works */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm">
          <h3 className="text-base font-display font-semibold m-0 mb-3 flex items-center gap-2 text-ink">
            <Cpu size={18} className="text-accent" /> How the ML Pipeline Works
          </h3>
          <ul className="text-xs text-ink-muted space-y-2 pl-4 list-disc m-0">
            <li>
              <strong>Oracle SQL Feature Extraction (<code className="text-accent">ml/extract.py</code>):</strong> Computes patient age via database function <code className="text-accent">calculate_age(dob)</code>, strictly historical appointment count, prior no-show counts, and lead-time days.
            </li>
            <li>
              <strong>Class Imbalance & Recall Optimization (<code className="text-accent">ml/evaluate.py</code>):</strong> Outpatient no-shows average ~12%. The model is chosen by <em>Recall first</em> to eliminate false negatives (unfilled doctor slots), treating false alarms as low-cost phone reminders.
            </li>
            <li>
              <strong>Offline Batch Pipeline (<code className="text-accent">ml/predict_and_store.py</code>):</strong> Uses atomic Oracle <code className="text-accent">MERGE INTO ml_prediction</code> so web clients only execute fast read-only queries.
            </li>
          </ul>
        </div>

        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm">
          <h3 className="text-base font-display font-semibold m-0 mb-3 flex items-center gap-2 text-ink">
            <Info size={18} className="text-accent" /> Running / Retraining the Pipeline
          </h3>
          <p className="text-xs text-ink-muted mb-2">
            The machine learning engine can be run on a schedule or on demand using the bundled scripts:
          </p>
          <div className="bg-surface-3 p-3 rounded-lg font-mono text-xs text-ink border border-border mb-2">
            # Run complete train + evaluate + score pipeline:<br />
            python ml/run_pipeline.py<br /><br />
            # Or run using PowerShell script:<br />
            .\4_run_ml.ps1
          </div>
          <div className="text-xs text-ink-muted">
            Includes automated cross-validation, feature scaling, model persistence (<code className="text-accent">no_show_model.joblib</code>), and database upserts.
          </div>
        </div>
      </div>
    </div>
  );
}