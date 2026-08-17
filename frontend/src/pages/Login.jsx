import React, { useState, useEffect } from 'react';
import { Shield, Loader2, AlertCircle, ArrowRight, Fingerprint, Network, Radar, Brain, Lock } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';
import { Input, Label } from '../components/ui/Input';

const HIGHLIGHTS = [
  { icon: Radar,       label: 'Onion Intelligence Probe', desc: 'Query Ahmia + Tor circuits in parallel.' },
  { icon: Network,     label: 'Correlation Engine',       desc: 'Merge fragmented leaks into master identities.' },
  { icon: Brain,       label: 'Local LLM Co-Analyst',     desc: 'Private AI that runs real NASO tools.' },
  { icon: Lock,        label: 'Audit-Grade Chain of Custody', desc: 'Every action hashed, signed, exportable.' },
];

// Which components /system/health reports on, in the order they matter to
// somebody looking at a login screen that will not let them in.
//
// These four rows used to be constants — TOR Circuit ACTIVE, Ahmia Index
// ONLINE, YARA Engine READY, Vault SEALED — with pulsing green dots, on a
// screen shown before anyone has authenticated. They said ACTIVE with the
// stack in pieces. `/system/health` is deliberately unauthenticated precisely
// so that something in this position can ask it.
const HEALTH_ROWS = [
  { key: 'database', label: 'Database' },
  { key: 'redis', label: 'Redis' },
  { key: 'elasticsearch', label: 'Search' },
  { key: 'rabbitmq', label: 'Task broker' },
];

const TONE_FOR = { ok: 'ok', degraded: 'err', disabled: 'warn' };

function TelemetryRow({ label, value, tone }) {
  const color =
    tone === 'ok' ? 'text-[#32D74B]' : tone === 'warn' ? 'text-[#FFD60A]' : tone === 'err' ? 'text-[#FF453A]' : 'text-zinc-500';
  const dot =
    tone === 'ok' ? 'bg-[#32D74B]' : tone === 'warn' ? 'bg-[#FFD60A]' : tone === 'err' ? 'bg-[#FF453A]' : 'bg-zinc-600';
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
      <span className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">{label}</span>
      <span className={`text-[11px] font-mono font-semibold flex items-center gap-1.5 ${color}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${dot} animate-pulse`} />
        {value}
      </span>
    </div>
  );
}

export default function Login() {
  const { login, isLoading, error, clearError } = useNasoStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cursorIdx, setCursorIdx] = useState(0);
  // Unauthenticated on purpose — see the docstring on /system/health. If it
  // cannot be reached at all, that is itself the most useful thing this panel
  // can tell somebody staring at a login form.
  const [health, setHealth] = useState(null);
  useEffect(() => {
    let cancelled = false;
    const probe = () =>
      fetch('/system/health')
        .then((r) => r.json())
        .then((d) => { if (!cancelled) setHealth(d); })
        .catch(() => { if (!cancelled) setHealth({ components: {} }); });
    probe();
    const t = setInterval(probe, 15000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  // Rotate highlighted capability card every 3.5s — static marketing is boring.
  useEffect(() => {
    const t = setInterval(() => setCursorIdx(i => (i + 1) % HIGHLIGHTS.length), 3500);
    return () => clearInterval(t);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    const success = await login(email, password);
    if (success !== false) {
      useNasoStore.getState().fetchMe();
    }
  };

  return (
    <div className="min-h-screen bg-black text-zinc-100 grid lg:grid-cols-[1fr_480px] overflow-hidden">
      {/* ──────────────── Hero panel ──────────────── */}
      <aside className="hidden lg:flex relative flex-col justify-between p-12 overflow-hidden border-r border-white/[0.06] bg-gradient-to-br from-[#0A84FF]/[0.05] via-transparent to-transparent">
        {/* Ambient mesh */}
        <div className="absolute -top-40 -left-40 w-[480px] h-[480px] rounded-full bg-[#0A84FF]/[0.09] blur-[140px] pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-[380px] h-[380px] rounded-full bg-[#5E5CE6]/[0.06] blur-[140px] pointer-events-none" />
        <div className="absolute inset-0 bg-grid-pattern opacity-40 pointer-events-none" />

        {/* Brand */}
        <header className="relative z-10 flex items-center gap-3">
          <div className="bg-[#0A84FF] p-2.5 rounded-2xl shadow-[0_0_24px_rgba(10,132,255,0.45)] animate-pulse-glow flex items-center justify-center">
            <img src="/naso-logo.svg" alt="" aria-hidden="true" className="w-5 h-5 animate-radar" />
          </div>
          <div className="flex flex-col">
            <span className="text-[16px] font-semibold tracking-tight text-white shimmer-text">NASO</span>
            <span className="text-[11px] text-zinc-400 font-medium tracking-wide">Forensic OS v0.1</span>
          </div>
        </header>

        {/* Headline */}
        <div className="relative z-10 space-y-6 max-w-xl">
          <p className="text-[11px] uppercase tracking-[0.3em] text-[#0A84FF] font-semibold">
            Intelligence Platform · Operator-grade
          </p>
          <h1 className="text-[clamp(28px,4vw,44px)] font-semibold tracking-tight leading-[1.08]">
            Correlate the <span className="text-[#0A84FF]">invisible</span>.
            <br />Hunt what leaked.
          </h1>
          <p className="text-[14px] text-zinc-400 max-w-md leading-relaxed">
            NASO unifies Tor reconnaissance, breach correlation, and an AI co-analyst
            under a single chain-of-custody ledger. Deploy a probe, merge identities,
            and ship a dossier — without leaving the console.
          </p>

          {/* Rotating capability card */}
          <div className="relative h-[76px]">
            {HIGHLIGHTS.map((h, i) => {
              const Icon = h.icon;
              const active = i === cursorIdx;
              return (
                <div
                  key={h.label}
                  className={`absolute inset-0 flex items-center gap-4 p-4 rounded-2xl border backdrop-blur-xl transition-all duration-500 ${
                    active
                      ? 'opacity-100 translate-y-0 bg-white/[0.04] border-white/[0.10]'
                      : 'opacity-0 translate-y-2 bg-transparent border-transparent pointer-events-none'
                  }`}
                  aria-hidden={!active}
                >
                  <div className="w-10 h-10 rounded-xl bg-[#0A84FF]/10 border border-[#0A84FF]/20 flex items-center justify-center shrink-0">
                    <Icon size={18} className="text-[#0A84FF]" strokeWidth={1.5} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-white tracking-tight">{h.label}</p>
                    <p className="text-[12px] text-zinc-500 truncate">{h.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination dots */}
          <div className="flex items-center gap-1.5">
            {HIGHLIGHTS.map((_, i) => (
              <button
                key={i}
                onClick={() => setCursorIdx(i)}
                aria-label={`Show highlight ${i + 1}`}
                className={`h-1 rounded-full transition-all ${
                  i === cursorIdx ? 'w-8 bg-[#0A84FF]' : 'w-3 bg-white/10 hover:bg-white/20'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Telemetry footer */}
        <div className="relative z-10 space-y-2 max-w-md">
          <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-600 font-semibold">Live telemetry</p>
          <div className="p-4 rounded-2xl bg-black/40 border border-white/[0.06] backdrop-blur-xl">
            {HEALTH_ROWS.map(({ key, label }) => {
              const status = health?.components?.[key]?.status;
              return (
                <TelemetryRow
                  key={key}
                  label={label}
                  value={status ? status.toUpperCase() : health === null ? 'CHECKING' : 'UNREACHABLE'}
                  tone={TONE_FOR[status] ?? 'muted'}
                />
              );
            })}
          </div>
        </div>
      </aside>

      {/* ──────────────── Auth panel ──────────────── */}
      <main className="flex items-center justify-center p-6 sm:p-10 relative">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#0A84FF]/[0.04] rounded-full blur-[120px] pointer-events-none lg:hidden" />

        <div className="w-full max-w-sm relative z-10">
          {/* Mobile brand */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="w-14 h-14 bg-white/[0.03] rounded-[18px] border border-white/[0.08] flex items-center justify-center mb-4 shadow-2xl relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-[#0A84FF]/20 to-transparent opacity-50" />
              <Shield size={26} className="text-[#0A84FF] relative z-10" strokeWidth={1.5} />
            </div>
            <h1 className="text-[24px] font-bold tracking-tight text-white">NASO</h1>
            <p className="text-[13px] text-zinc-500 mt-0.5">Forensic Intelligence Platform</p>
          </div>

          <div className="hidden lg:block mb-8">
            <h2 className="text-[22px] font-semibold tracking-tight text-white">Operator sign-in</h2>
            <p className="text-[13px] text-zinc-500 mt-1">Authenticate against the central vault to open a forensic session.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" aria-label="Sign in">
            <div>
              <Label htmlFor="login-email">Email</Label>
              <Input
                id="login-email"
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); if (error) clearError(); }}
                placeholder="operator@naso.local"
                autoFocus
                autoComplete="username"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label htmlFor="login-password" className="mb-0">Password</Label>
                <a href="#" className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors" onClick={e => e.preventDefault()}>
                  Recovery SOP
                </a>
              </div>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); if (error) clearError(); }}
                placeholder="Enter credentials"
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div role="alert" className="flex items-center gap-2.5 p-3 rounded-xl bg-[#FF453A]/10 border border-[#FF453A]/20">
                <AlertCircle size={14} className="text-[#FF453A] shrink-0" strokeWidth={2} />
                <span className="text-[12px] font-medium text-[#FF453A]">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || !email || !password}
              className="group w-full h-11 bg-[#0A84FF] hover:bg-[#007AFF] disabled:bg-[#0A84FF]/50 disabled:cursor-not-allowed text-white text-[14px] font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 mt-2 shadow-lg shadow-[#0A84FF]/20"
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <>
                  Authenticate
                  <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" strokeWidth={2} />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <div className="flex items-start gap-3">
              <Fingerprint size={14} className="text-zinc-500 mt-0.5 shrink-0" strokeWidth={1.5} />
              <p className="text-[11px] text-zinc-500 leading-relaxed">
                Secured by signed JWT in an HTTP-only cookie.
                Every session is cryptographically audited.
              </p>
            </div>
          </div>

          <p className="text-center text-[10px] text-zinc-700 mt-6 font-mono">
            NASO · Forensic OS · © {new Date().getFullYear()}
          </p>
        </div>
      </main>
    </div>
  );
}
