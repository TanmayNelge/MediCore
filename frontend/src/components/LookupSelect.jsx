import { useLookup } from "../lib/lookups";
import { useAuth } from "../AuthContext";
import Field from "./Field";

const inputCls = "w-full rounded-md border border-border-strong px-3 py-2 text-sm bg-surface focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition";

export default function LookupSelect({
  label, value, onChange, lookupPath, labelFn, placeholder = "Select…",
  hint, required, fallbackPlaceholder = "Enter ID",
}) {
  const { auth } = useAuth();
  const { options, unavailable, loading } = useLookup(lookupPath, { token: auth.token, labelFn });

  if (unavailable || !lookupPath) {
    return (
      <Field label={label} hint={hint || "Free-text ID (lookup endpoint unavailable)"}>
        <input
          className={inputCls}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={fallbackPlaceholder}
          required={required}
        />
      </Field>
    );
  }

  return (
    <Field label={label} hint={hint}>
      <select
        className={inputCls}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        disabled={loading}
      >
        <option value="">{loading ? "Loading…" : placeholder}</option>
        {(options || []).map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Field>
  );
}