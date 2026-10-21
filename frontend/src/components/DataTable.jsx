import { useMemo } from "react";
import { Download } from "lucide-react";
import EmptyState from "./EmptyState";
import { humanizeKey, dash } from "../lib/format";

export default function DataTable({ rows, emptyMessage = "No rows yet.", filename = "results.csv", maxHeight }) {
  const cols = useMemo(() => (rows && rows.length ? Object.keys(rows[0]) : []), [rows]);

  if (!rows || rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  function exportCsv() {
    const esc = (v) => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const lines = [cols.join(",")];
    rows.forEach((r) => lines.push(cols.map((c) => esc(r[c])).join(",")));
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-ink-faint">{rows.length} row{rows.length !== 1 ? "s" : ""}</span>
        <button className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-ink-muted hover:bg-white hover:text-accent-strong border border-transparent hover:border-border transition-colors" onClick={exportCsv} title="Export CSV">
          <Download size={14} /> CSV
        </button>
      </div>
      <div className="overflow-x-auto border border-border rounded-lg bg-surface shadow-sm" style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-3/70 text-ink-muted text-[0.72rem] uppercase tracking-wider">
              {cols.map((c) => (
                <th key={c} className="text-left px-3.5 py-2.5 font-semibold border-b border-border-strong sticky top-0 bg-[#e7efed]">
                  {humanizeKey(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="even:bg-surface-2/50 hover:bg-accent-soft/60 transition-colors">
                {cols.map((c) => {
                  const v = r[c];
                  const empty = v === null || v === undefined || v === "";
                  return (
                    <td key={c} className={`px-3.5 py-2.5 border-b border-border/70 ${empty ? "text-ink-faint italic" : ""}`}>
                      {empty ? dash(v) : String(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}