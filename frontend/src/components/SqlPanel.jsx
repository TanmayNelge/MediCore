import { useState } from "react";
import { Code2, Copy, Check, ChevronDown } from "lucide-react";

export default function SqlPanel({ sql }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!sql) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      const pre = document.querySelector("pre[data-sql-panel]");
      if (pre && window.getSelection) {
        const range = document.createRange();
        range.selectNodeContents(pre);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
    }
  }

  return (
    <div className="mt-4">
      <button
        className="inline-flex items-center gap-1.5 bg-surface border border-border-strong text-accent-strong rounded-md px-3 py-1.5 text-[0.78rem] hover:bg-accent-soft transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <Code2 size={14} />
        {open ? "Hide" : "Show"} SQL executed
        <ChevronDown size={13} className="transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }} />
      </button>
      {open && (
        <div className="mt-2.5 rounded-lg bg-structure border border-structure-3 p-4">
          <div className="flex justify-between items-start gap-4">
            <pre
              data-sql-panel
              className="m-0 flex-1 font-mono text-[0.82rem] text-[#d9ece8] whitespace-pre-wrap break-words"
            >
              {sql}
            </pre>
            <button
              className="inline-flex items-center gap-1.5 bg-transparent border border-[#3a5a54] text-[#d9ece8] rounded-md px-2.5 py-1.5 text-xs hover:bg-white/5 transition-colors"
              onClick={copy}
            >
              {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}