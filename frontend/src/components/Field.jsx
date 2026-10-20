export default function Field({ label, hint, error, children, htmlFor, className = "" }) {
  return (
    <div className={`mb-3.5 ${className}`}>
      {label && <label htmlFor={htmlFor} className="block text-xs font-medium text-ink-soft mb-1">{label}</label>}
      {children}
      {hint && !error && <div className="text-[0.7rem] text-ink-faint mt-1">{hint}</div>}
      {error && <div className="text-[0.7rem] text-urgent mt-1">{error}</div>}
    </div>
  );
}