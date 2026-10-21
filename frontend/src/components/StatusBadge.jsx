const MAP = {
  SCHEDULED: "neutral", COMPLETED: "ok", CANCELLED: "urgent", NO_SHOW: "urgent",
  PENDING: "warn", IN_PROGRESS: "warn", AVAILABLE: "ok", OCCUPIED: "warn",
  PAID: "ok", PARTIALLY_PAID: "warn", UNPAID: "urgent",
  ACTIVE: "ok", INACTIVE: "neutral", DISCHARGED: "neutral",
  WAITING: "warn", CALLED: "ok",
  LOW: "ok", MEDIUM: "warn", HIGH: "urgent",
};

const CLASSES = {
  ok:      "bg-ok-soft text-ok",
  warn:    "bg-warn-soft text-warn",
  urgent:  "bg-urgent-soft text-urgent",
  neutral: "bg-surface-3 text-ink-muted",
};

export default function StatusBadge({ status }) {
  if (status == null || status === "") {
    return <span className="inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full bg-surface-3 text-ink-muted">—</span>;
  }
  const cls = MAP[String(status).toUpperCase()] || "neutral";
  return (
    <span className={`inline-flex items-center text-[0.73rem] font-medium px-2.5 py-0.5 rounded-full ${CLASSES[cls]}`}>
      {status}
    </span>
  );
}