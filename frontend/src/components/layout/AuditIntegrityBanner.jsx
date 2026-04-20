import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useNasoStore from '@/store/useNasoStore';
import { ShieldAlert, AlertTriangle, ExternalLink, X } from 'lucide-react';

// Dismissal is per-tab + per-break: we key sessionStorage on the broken
// row's position so a NEW tamper event after dismissal re-shows the banner
// immediately. ``_integrity_error`` covers the network-error case.
function _dismissKey(snapshot) {
  if (!snapshot) return null;
  if (snapshot.ok === null) return 'naso.audit_dismissed:_integrity_error';
  return `naso.audit_dismissed:broken_at_${snapshot.broken_at}`;
}

function _isDismissed(snapshot) {
  try {
    const key = _dismissKey(snapshot);
    if (!key) return false;
    return window.sessionStorage.getItem(key) === '1';
  } catch {
    return false;
  }
}

function _markDismissed(snapshot) {
  try {
    const key = _dismissKey(snapshot);
    if (key) window.sessionStorage.setItem(key, '1');
  } catch { /* no-op — the UI still handles the transient dismiss state below */ }
}

/**
 * Persistent top-of-shell banner that screams when the audit chain is
 * broken (or the verification call itself fails). Invisible when the
 * chain is healthy; otherwise survives route changes and is dismissible
 * only for the current tab's session.
 */
export default function AuditIntegrityBanner() {
  const auditIntegrity = useNasoStore(s => s.auditIntegrity);
  const refreshAuditIntegrity = useNasoStore(s => s.refreshAuditIntegrity);
  const isAuthenticated = useNasoStore(s => s.isAuthenticated);
  const [dismissed, setDismissed] = useState(false);
  const navigate = useNavigate();

  // Kick off an initial background verification as soon as the user is in.
  // The store's TTL guard ensures this stays cheap on re-mount.
  useEffect(() => {
    if (isAuthenticated) refreshAuditIntegrity();
  }, [isAuthenticated, refreshAuditIntegrity]);

  // Re-evaluate dismissal each time the snapshot shape changes — a new
  // break means a different sessionStorage key, so a prior dismissal
  // no longer applies.
  useEffect(() => {
    setDismissed(_isDismissed(auditIntegrity));
  }, [auditIntegrity?.broken_at, auditIntegrity?.ok]);

  if (!isAuthenticated || !auditIntegrity) return null;
  // Healthy chain → no banner, ever.
  if (auditIntegrity.ok === true) return null;
  if (dismissed) return null;

  const isError = auditIntegrity.ok === null;
  const tone = isError
    ? {
        bg: 'bg-[#FFD60A]/[0.08]',
        border: 'border-[#FFD60A]/25',
        accent: 'bg-[#FFD60A]/20 text-[#FFD60A]',
        icon: AlertTriangle,
        title: 'Audit integrity check failed to run',
        body: auditIntegrity.error ?? 'The verification endpoint did not respond.',
      }
    : {
        bg: 'bg-[#FF453A]/[0.10]',
        border: 'border-[#FF453A]/30',
        accent: 'bg-[#FF453A]/20 text-[#FF453A]',
        icon: ShieldAlert,
        title: 'Audit chain integrity broken',
        body:
          `Row ${auditIntegrity.broken_at ?? '?'} failed verification` +
          (auditIntegrity.reason ? ` — ${auditIntegrity.reason}` : '') +
          '.',
      };

  const Icon = tone.icon;

  const onDismiss = () => {
    _markDismissed(auditIntegrity);
    setDismissed(true);
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`relative border-b ${tone.border} ${tone.bg} backdrop-blur-xl`}
    >
      <div className="flex items-center gap-3 px-4 sm:px-6 py-2.5 max-w-[1600px] mx-auto">
        <div className={`w-7 h-7 rounded-full ${tone.accent} flex items-center justify-center shrink-0`}>
          <Icon size={14} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-[12px] font-semibold ${isError ? 'text-[#FFD60A]' : 'text-[#FF453A]'} tracking-tight`}>
            {tone.title}
          </p>
          <p className="text-[11px] text-zinc-400 truncate">{tone.body}</p>
        </div>
        <button
          onClick={() => navigate('/audit')}
          className={`hidden sm:inline-flex items-center gap-1.5 h-7 px-3 rounded-full border text-[11px] font-medium transition-colors ${tone.border} ${isError ? 'text-[#FFD60A] hover:bg-[#FFD60A]/10' : 'text-[#FF453A] hover:bg-[#FF453A]/10'}`}
        >
          <ExternalLink size={11} strokeWidth={2} /> View audit log
        </button>
        <button
          onClick={() => refreshAuditIntegrity({ force: true })}
          className="hidden sm:inline-flex h-7 px-3 rounded-full border border-white/[0.10] text-[11px] font-medium text-zinc-300 hover:bg-white/5 transition-colors"
          title="Re-run verification"
        >
          Re-check
        </button>
        <button
          onClick={onDismiss}
          aria-label="Dismiss for this session"
          className="w-6 h-6 rounded-md text-zinc-500 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors shrink-0"
        >
          <X size={13} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
