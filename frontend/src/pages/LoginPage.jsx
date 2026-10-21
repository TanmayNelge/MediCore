import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { ShieldCheck, Eye, EyeOff, Loader2, User, Lock, Database, Brain } from "lucide-react";
import EcgLine from "../components/EcgLine";

const FEATURES = [
  { icon: Lock, title: "Role-based", text: "Seven roles, least privilege" },
  { icon: Database, title: "Live SQL", text: "See every query executed" },
  { icon: Brain, title: "AI insights", text: "No-show risk scoring" },
];

const DEMO = [
  ["admin1", "Full access"], ["doctor1", "Clinical"], ["nurse1", "Triage"],
  ["receptionist1", "Front desk"], ["labtech1", "Lab"], ["pharmacist1", "Pharmacy"],
  ["billingclerk1", "Billing"],
];

export default function LoginPage() {
  const [username, setUsername] = useState("doctor1");
  const [password, setPassword] = useState("doctor1");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      const res = await fetch("/api/auth/login", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Login failed");
      login(data.access_token, data.role, username);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = "w-full rounded-lg border border-border-strong bg-white px-3.5 py-2.5 text-sm focus:border-accent focus:ring-4 focus:ring-accent/15 outline-none transition";

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      {/* ---------- Left: brand artwork ---------- */}
      <div className="hidden lg:flex flex-col justify-between p-12 text-white relative overflow-hidden bg-hero">
        <div className="absolute inset-0 bg-dots" />
        {/* glowing orbs */}
        <div className="absolute -top-24 -right-24 h-96 w-96 rounded-full bg-accent-bright/20 blur-3xl animate-float" />
        <div className="absolute bottom-10 -left-24 h-80 w-80 rounded-full bg-accent/30 blur-3xl animate-float-slow" />
        {/* giant faint cross */}
        <svg className="absolute -right-16 top-1/2 -translate-y-1/2 h-[520px] w-[520px] text-white/[0.04]" viewBox="0 0 100 100" fill="currentColor" aria-hidden="true">
          <path d="M38 6h24v32h32v24H62v32H38V62H6V38h32z" />
        </svg>
        {/* concentric rings */}
        <svg className="absolute -left-40 -bottom-40 h-[560px] w-[560px] text-white/10" viewBox="0 0 200 200" fill="none" stroke="currentColor" aria-hidden="true">
          <circle cx="100" cy="100" r="95" /><circle cx="100" cy="100" r="72" /><circle cx="100" cy="100" r="49" /><circle cx="100" cy="100" r="26" />
        </svg>
        {/* heartbeat line */}
        <EcgLine className="absolute left-0 right-0 top-[44%] h-36 w-full" />

        <div className="relative z-10 flex items-center gap-3">
          <img src="/favicon.svg" alt="MediCore" className="h-11 w-11 rounded-xl border border-white/20 shadow-md" />
          <span className="font-display text-2xl font-semibold tracking-tight">MediCore</span>
        </div>

        <div className="relative z-10 max-w-xl">
          <span className="inline-flex items-center gap-2 glass rounded-full px-3 py-1 text-xs text-[#cfe9e2] mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-bright animate-pulse" /> Secure clinical workspace
          </span>
          <h1 className="text-5xl font-display font-semibold text-white leading-[1.08] mb-5">
            Hospital &amp; Clinic<br />Management System
          </h1>
          <p className="text-[#b3d1c9] text-lg max-w-md mb-9">
            One database. Every role. Real SQL, real Oracle, real access control.
          </p>
          <div className="grid grid-cols-3 gap-3 max-w-lg">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="glass rounded-xl p-3.5">
                <Icon size={18} className="text-accent-bright mb-2" />
                <div className="text-sm font-semibold text-white">{title}</div>
                <div className="text-[0.72rem] text-[#a3c4bb] leading-snug mt-0.5">{text}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-xs text-[#7fa79d]">
          Oracle XE · FastAPI · React · scikit-learn
        </div>
      </div>

      {/* ---------- Right: sign-in ---------- */}
      <div className="relative flex items-center justify-center p-6 sm:p-10 overflow-hidden">
        <div className="absolute -top-32 -right-32 h-80 w-80 rounded-full bg-accent-bright/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-32 h-80 w-80 rounded-full bg-accent/15 blur-3xl" />
        <div className="relative w-full max-w-md animate-rise">
          <div className="lg:hidden flex items-center gap-2.5 mb-6">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-structure">
              <ShieldCheck size={22} className="text-accent-bright" />
            </span>
            <span className="font-display text-2xl font-semibold">MediCore</span>
          </div>

          <div className="bg-white/90 backdrop-blur-xl border border-white rounded-2xl shadow-xl p-7 sm:p-9 ring-1 ring-border">
            <h2 className="text-3xl font-display font-semibold mb-1">Welcome back</h2>
            <p className="text-sm text-ink-muted mb-7">Sign in with your role (password matches username, e.g. <span className="font-mono text-accent font-medium">doctor1</span> / <span className="font-mono text-accent font-medium">doctor1</span>).</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink-soft mb-1.5">Username</label>
                <div className="relative">
                  <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="doctor1"
                    autoComplete="username"
                    className={`${inputCls} pl-10`}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-soft mb-1.5">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
                  <input
                    type={showPwd ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className={`${inputCls} pl-10 pr-10`}
                  />
                  <button type="button" aria-label={showPwd ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-ink-muted hover:text-ink rounded-md hover:bg-surface-3 transition-colors" onClick={() => setShowPwd((s) => !s)}>
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              {error && (
                <p className="text-sm text-urgent bg-urgent-soft border border-urgent/20 rounded-lg px-3 py-2">{error}</p>
              )}
              <button type="submit" disabled={loading} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-b from-accent to-accent-strong hover:brightness-110 text-white rounded-lg py-2.5 text-sm font-semibold shadow-md shadow-accent/30 transition disabled:opacity-60">
                {loading && <Loader2 size={15} className="animate-spin" />}
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <div className="mt-7 pt-6 border-t border-border">
              <div className="text-[0.7rem] uppercase tracking-wider font-semibold text-ink-faint mb-2.5">Demo accounts — click to auto-fill</div>
              <div className="flex flex-wrap gap-1.5">
                {DEMO.map(([u, note]) => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => { setUsername(u); setPassword(u); }}
                    title={note}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      username === u
                        ? "bg-accent-soft border-accent text-accent-strong font-medium"
                        : "bg-surface-2 border-border text-ink-muted hover:border-accent hover:text-accent-strong"
                    }`}
                  >
                    <span className="font-mono">{u}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
