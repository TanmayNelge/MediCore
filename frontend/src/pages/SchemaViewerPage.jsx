import { useMemo, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import DataTable from "../components/DataTable";
import { useAuth } from "../AuthContext";
import { apiFetch } from "../api";
import { useApi } from "../lib/useApi";
import SqlPanel from "../components/SqlPanel";
import PageHeader from "../components/PageHeader";
import { Columns3, ChevronDown, KeyRound, Link2, Search, RefreshCw } from "lucide-react";

function TableBlock({ table, cols }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-surface border border-border rounded-xl p-5 mb-3 shadow-sm">
      <div className="flex justify-between items-center cursor-pointer" onClick={() => setOpen((o) => !o)}>
        <div className="flex items-center gap-2.5">
          <h3 className="text-base font-display m-0">{table}</h3>
          <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-surface-3 text-ink-muted">{cols.length} cols</span>
        </div>
        <ChevronDown size={18} className="text-ink-muted transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }} />
      </div>
      {open && (
        <div className="mt-4 overflow-x-auto border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-2 text-ink-muted text-[0.74rem] uppercase tracking-wider">
                <th className="text-left px-3.5 py-2.5 font-semibold border-b border-border">Column</th>
                <th className="text-left px-3.5 py-2.5 font-semibold border-b border-border">Type</th>
                <th className="text-left px-3.5 py-2.5 font-semibold border-b border-border">Nullable</th>
                <th className="text-left px-3.5 py-2.5 font-semibold border-b border-border">Keys</th>
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => (
                <tr key={c.column_name} className="hover:bg-surface-2 transition-colors">
                  <td className="px-3.5 py-2.5 border-b border-[#e8eeec] font-mono text-[0.82rem]">{c.column_name}</td>
                  <td className="px-3.5 py-2.5 border-b border-[#e8eeec] text-sm">{c.data_type}</td>
                  <td className="px-3.5 py-2.5 border-b border-[#e8eeec] text-sm">{c.nullable}</td>
                  <td className="px-3.5 py-2.5 border-b border-[#e8eeec]">
                    {c.is_pk && <span className="inline-flex items-center gap-1 text-[0.73rem] font-medium px-2 py-0.5 rounded-full bg-accent-soft text-accent-strong"><KeyRound size={11} /> PK</span>}{" "}
                    {c.is_fk && <span className="inline-flex items-center gap-1 text-[0.73rem] font-medium px-2 py-0.5 rounded-full bg-warn-soft text-warn"><Link2 size={11} /> FK</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function SchemaViewerPage() {
  const { auth } = useAuth();
  const [query, setQuery] = useState("");
  const fetcher = useCallback((token) => apiFetch("/schema/columns", { token }), []);
  const { data, loading, error, reload } = useApi(fetcher);
  const objFetcher = useCallback((token) => apiFetch("/schema/objects", { token }), []);
  const objects = useApi(objFetcher);
  const [tab, setTab] = useState("tables");
  const TABS = [["tables", "Tables & columns"], ["views", "Views"], ["indexes", "Indexes"], ["triggers", "Triggers"],
                ["plsql", "Procedures / functions / packages"], ["sequences", "Sequences"], ["constraints", "Constraints"]];

  const byTable = useMemo(() => {
    const map = {};
    (data?.results || []).forEach((row) => {
      map[row.table_name] = map[row.table_name] || [];
      map[row.table_name].push(row);
    });
    return map;
  }, [data]);

  const filteredTables = useMemo(() => {
    const q = query.trim().toLowerCase();
    return Object.entries(byTable)
      .filter(([t, cols]) =>
        !q || t.toLowerCase().includes(q) || cols.some((c) => c.column_name.toLowerCase().includes(q))
      )
      .sort(([a], [b]) => a.localeCompare(b));
  }, [byTable, query]);

  return (
    <div>
      <PageHeader
        title="Schema viewer"
        subtitle={`Live from Oracle's data dictionary (ALL_TAB_COLUMNS, ALL_CONSTRAINTS, ALL_TRIGGERS …) — never hardcoded. You see what your Oracle role (${auth?.username}) is allowed to see.`}
        actions={
          <button className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-2 text-sm hover:bg-accent-soft transition-colors disabled:opacity-50" onClick={reload} disabled={loading}>
            <RefreshCw size={15} /> Refresh
          </button>
        }
      />

      <div className="flex gap-1.5 flex-wrap mb-4">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`rounded-md px-3 py-1.5 text-sm border transition-colors ${tab === k ? "bg-accent text-white border-accent" : "bg-surface border-border-strong text-accent-strong hover:bg-accent-soft"}`}>
            {label}{k !== "tables" && objects.data?.[k] ? ` (${objects.data[k].length})` : k === "tables" ? ` (${Object.keys(byTable).length})` : ""}
          </button>
        ))}
        <Link to="/er-model" className="rounded-md px-3 py-1.5 text-sm border border-border-strong text-ink-soft hover:bg-accent-soft ml-auto">View ER diagram →</Link>
        <Link to="/normalization" className="rounded-md px-3 py-1.5 text-sm border border-border-strong text-ink-soft hover:bg-accent-soft">Keys & normalization →</Link>
      </div>

      {tab !== "tables" && (
        <div className="bg-surface border border-border rounded-xl p-5 mb-5 shadow-sm">
          {objects.loading && !objects.data && <div className="h-24 bg-surface-3 rounded animate-pulse" />}
          {objects.error && <p className="text-urgent">{objects.error}</p>}
          {objects.data && <>
            <DataTable rows={objects.data[tab]} filename={`${tab}.csv`} maxHeight={600} />
            <SqlPanel sql={objects.data.sql_executed} />
          </>}
        </div>
      )}

      {tab === "tables" && <>
      <div className="bg-surface border border-border rounded-xl p-4 mb-5 shadow-sm">
        <div className="flex items-center gap-2.5">
          <Search size={16} className="text-ink-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter tables or columns…"
            className="flex-1 border-none outline-none bg-transparent text-sm"
          />
          <span className="text-xs text-ink-faint">{filteredTables.length} table{filteredTables.length !== 1 ? "s" : ""}</span>
        </div>
      </div>

      {loading && !data && (
        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm">
          <div className="h-10 bg-surface-3 rounded animate-pulse mb-2" />
          <div className="h-10 bg-surface-3 rounded animate-pulse mb-2" />
          <div className="h-10 bg-surface-3 rounded animate-pulse" />
        </div>
      )}
      {error && <p className="text-urgent">{error}</p>}

      {filteredTables.map(([table, cols]) => <TableBlock key={table} table={table} cols={cols} />)}

      {filteredTables.length === 0 && data && (
        <div className="text-center py-10 text-ink-muted">
          <Columns3 size={28} className="mx-auto mb-2 text-ink-faint" />
          <div>No tables match "{query}".</div>
        </div>
      )}

      {data && <SqlPanel sql={data.sql_executed} />}
      </>}
    </div>
  );
}