import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";

const ToastContext = createContext(null);
let counter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const remove = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((message, kind = "success", ttl = 4000) => {
    const id = ++counter;
    setToasts((t) => [...t, { id, message, kind }]);
    if (ttl > 0) setTimeout(() => remove(id), ttl);
    return id;
  }, [remove]);
  const success = useCallback((m) => push(m, "success"), [push]);
  const error = useCallback((m) => push(m, "error"), [push]);

  return (
    <ToastContext.Provider value={{ success, error, push }}>
      {children}
      <div className="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-start gap-2.5 rounded-lg bg-white/95 backdrop-blur-md px-3.5 py-3 text-sm shadow-xl border border-border ${
              t.kind === "error" ? "border-l-4 border-l-urgent" : "border-l-4 border-l-ok"
            }`}
          >
            {t.kind === "success"
              ? <CheckCircle2 size={18} className="text-ok shrink-0" />
              : <AlertCircle size={18} className="text-urgent shrink-0" />}
            <span className="flex-1">{t.message}</span>
            <button className="text-ink-muted hover:text-ink" onClick={() => remove(t.id)}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}