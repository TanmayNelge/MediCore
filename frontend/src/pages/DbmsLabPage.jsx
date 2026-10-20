import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthContext";
import { apiFetch, apiCall } from "../api";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import { Database, ChevronDown, Play, Search, Loader2 } from "lucide-react";

const panelCls = "bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm";

function ConceptRow({ concept, token }) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true); setError(null);
    try {
      const res = await apiCall("/dbms-lab/execute", { token, params: { query: concept.canonical_query } });
      setResult(res);
    } catch (err) { setError(err.message); }
    finally { setRunning(false); }
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5 mb-3 shadow-sm">
      <div className="flex justify-between items-center gap-4 cursor-pointer" onClick={() => setOpen((o) => !o)}>
        <div className="flex items-center gap-2.5">
          <h3 className="text-base font-display m-0">{concept.name}</h3>
          {concept.executable
            ? <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-ok-soft text-ok">runnable</span>
            : <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-surface-3 text-ink-muted">reference</span>}
        </div>
        <ChevronDown size={18} className="text-ink-muted transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }} />
      </div>
      {open && (
        <div className="mt-4">
          <p className="text-ink-muted text-sm">{concept.theory}</p>
          <pre className="bg-structure text-[#d9ece8] rounded-md p-4 font-mono text-[0.8rem] whitespace-pre-wrap break-words mb-3">{concept.canonical_query}</pre>
          {concept.executable ? (
            <button onClick={run} disabled={running} className="inline-flex items-center gap-1.5 bg-accent hover:bg-accent-strong text-white rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50">
              {running ? <><Loader2 size={14} className="animate-spin" /> Running…</> : <><Play size={14} /> Execute</>}
            </button>
          ) : (
            <p className="text-ink-muted text-xs">Not a SELECT — shown for reference only, not runnable through the sandboxed endpoint.</p>
          )}
          {error && <p className="text-urgent mt-2">{error}</p>}
          {result && <div className="mt-4"><DataTable rows={result.results} filename="dbms-lab.csv" /></div>}
        </div>
      )}
    </div>
  );
}

export default function DbmsLabPage() {
  const { auth } = useAuth();
  const [concepts, setConcepts] = useState([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    apiFetch("/dbms-lab/concepts", { token: auth.token }).then((d) => setConcepts(d.concepts || []));
  }, [auth.token]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return concepts;
    return concepts.filter((c) => c.name.toLowerCase().includes(q) || (c.theory || "").toLowerCase().includes(q));
  }, [concepts, query]);

  return (
    <div>
      <PageHeader title="DBMS concept lab" subtitle="The 20 categories from the brief, each backed by the exact query already in this project." />

      <div className={panelCls}>
        <div className="flex items-center gap-2.5">
          <Search size={16} className="text-ink-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter concepts…"
            className="flex-1 border-none outline-none bg-transparent text-sm"
          />
          <span className="text-xs text-ink-faint">{filtered.length} / {concepts.length}</span>
        </div>
      </div>

      {filtered.map((c) => <ConceptRow key={c.id} concept={c} token={auth.token} />)}
      {filtered.length === 0 && concepts.length > 0 && (
        <div className="text-center py-10 text-ink-muted">
          <Database size={28} className="mx-auto mb-2 text-ink-faint" />
          <div>No concepts match "{query}".</div>
        </div>
      )}
    </div>
  );
}