import { useState } from "react";
import { ChevronDown } from "lucide-react";

export default function CollapsibleSection({ title, icon: Icon, badge, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="bg-surface border border-border rounded-xl mb-5 shadow-sm overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left hover:bg-surface-2 transition-colors"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <h2 className="text-lg font-display m-0 flex items-center gap-2">
          {Icon && <Icon size={18} className="text-accent" />} {title}
          {badge}
        </h2>
        <ChevronDown size={18} className="text-ink-muted transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }} />
      </button>
      {open && <div className="px-5 pb-5 pt-1 border-t border-border animate-fade">{children}</div>}
    </section>
  );
}
