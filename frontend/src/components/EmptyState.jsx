import { Inbox } from "lucide-react";

export default function EmptyState({ icon: Icon = Inbox, title = "Nothing here yet", message, children }) {
  return (
    <div className="text-center py-12 px-4 bg-surface-2/70 border border-dashed border-border-strong rounded-xl">
      <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent-strong">
        <Icon size={22} />
      </span>
      <div className="font-display text-base font-semibold text-ink">{title}</div>
      {message && <p className="text-sm text-ink-muted mt-1 mb-0">{message}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}
