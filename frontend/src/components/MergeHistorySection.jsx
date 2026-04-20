import React, { useEffect, useState } from 'react';
import useNasoStore from '@/store/useNasoStore';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { GitMerge, Undo2, ShieldAlert, Fingerprint, CheckCircle2, Clock } from 'lucide-react';

// Presentational: one row per MergeEvent returned by
// GET /identities/{id}/merges. Renders the counterpart identifier, the
// role the focal identity played (master / slave), confidence score, and
// an inline Reverse button for active merges.
function MergeEventRow({ event, onReverse, pending }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');

  const isActive = event.is_active;
  const asMaster = event.role === 'master';
  const counter = event.counterpart;

  const timestamp = event.performed_at ? new Date(event.performed_at).toLocaleString() : '—';
  const reversedAt = event.reversed_at ? new Date(event.reversed_at).toLocaleString() : null;

  return (
    <div className={`rounded-xl border p-3 transition-colors ${
      isActive
        ? 'bg-black/30 border-white/[0.06]'
        : 'bg-zinc-900/40 border-white/[0.04] opacity-70'
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`p-1.5 rounded-lg ${asMaster ? 'bg-[#0A84FF]/10' : 'bg-[#FFD60A]/10'}`}>
            <GitMerge size={13} strokeWidth={1.8} className={asMaster ? 'text-[#0A84FF]' : 'text-[#FFD60A]'} />
          </div>
          <div className="min-w-0">
            <p className="text-[12px] font-medium text-white tracking-tight">
              {asMaster ? 'Absorbed' : 'Merged into'}
              <span className="text-zinc-500 font-normal">
                {' '}{asMaster ? '←' : '→'}{' '}
              </span>
              <span className="font-mono text-zinc-300">
                {counter?.identifier ?? counter?.id?.slice(0, 10) ?? 'unknown'}
              </span>
            </p>
            <p className="text-[10px] text-zinc-500 font-mono">
              {timestamp} · confidence {event.confidence} · {event.evidence_count} evidence
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isActive ? (
            <Badge variant="outline" className="text-[9px] border-[#32D74B]/30 text-[#32D74B] bg-[#32D74B]/10">
              <CheckCircle2 size={9} className="mr-1" strokeWidth={2} /> ACTIVE
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[9px] border-zinc-700 text-zinc-500 bg-zinc-900">
              <Undo2 size={9} className="mr-1" strokeWidth={2} /> REVERSED
            </Badge>
          )}
          {isActive && asMaster && (
            <button
              onClick={() => setOpen(o => !o)}
              className="text-[10px] font-medium text-[#FF453A] hover:text-[#FF6B63] transition-colors"
              disabled={pending}
            >
              Reverse
            </button>
          )}
        </div>
      </div>

      {/* Inline reverse form — keeps the UX local, no extra modal. */}
      {open && isActive && (
        <div className="mt-3 pt-3 border-t border-white/[0.04] space-y-2">
          <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Reason (required for audit trail)
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. false positive — different people"
            className="w-full bg-black/40 border border-white/[0.08] rounded-lg px-3 py-1.5 text-[12px] text-white placeholder:text-zinc-600 focus:border-[#FF453A]/40 focus:outline-none focus:ring-1 focus:ring-[#FF453A]/20"
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => { setOpen(false); setReason(''); }}
              className="h-7 px-3 text-[11px] text-zinc-400 hover:text-white"
            >
              Cancel
            </Button>
            <Button
              onClick={async () => {
                await onReverse(event.id, reason);
                setOpen(false);
                setReason('');
              }}
              disabled={!reason.trim() || pending}
              className="h-7 px-3 text-[11px] bg-[#FF453A] hover:bg-[#E3372F] text-white font-medium rounded-md shadow-sm"
            >
              Confirm reversal
            </Button>
          </div>
        </div>
      )}

      {/* Audit tail for reversed merges — the operator can see why. */}
      {!isActive && event.reverse_reason && (
        <div className="mt-2 pt-2 border-t border-white/[0.04] text-[10px] text-zinc-500">
          <span className="uppercase tracking-wider font-medium">Reversed</span>
          {' · '}{reversedAt}
          {' · '}<span className="italic">{event.reverse_reason}</span>
        </div>
      )}
    </div>
  );
}

export default function MergeHistorySection({ identityId }) {
  const events = useNasoStore(s => s.identityMergeHistory[identityId] || []);
  const fetchIdentityMergeHistory = useNasoStore(s => s.fetchIdentityMergeHistory);
  const reverseMerge = useNasoStore(s => s.reverseMerge);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (identityId) fetchIdentityMergeHistory(identityId);
  }, [identityId, fetchIdentityMergeHistory]);

  if (!identityId) return null;
  const total = events.length;
  const active = events.filter(e => e.is_active).length;

  const handleReverse = async (eventId, reason) => {
    setPending(true);
    try {
      await reverseMerge(eventId, reason);
    } finally {
      setPending(false);
    }
  };

  if (total === 0) {
    return (
      <div className="space-y-3">
        <h4 className="text-[13px] font-semibold text-zinc-300 flex items-center gap-2">
          <GitMerge size={15} strokeWidth={1.5} /> Merge Provenance
        </h4>
        <div className="bg-black/30 border border-white/[0.05] rounded-xl p-4 text-center">
          <ShieldAlert size={24} strokeWidth={1.2} className="text-zinc-700 mx-auto mb-2" />
          <p className="text-[11px] text-zinc-500">
            No merge events — this identity has always been standalone.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-[13px] font-semibold text-zinc-300 flex items-center gap-2">
          <GitMerge size={15} strokeWidth={1.5} /> Merge Provenance
          <Badge className="ml-1 bg-white/5 text-zinc-400 border border-white/10 text-[10px]">
            {active} active
          </Badge>
          {active !== total && (
            <Badge className="bg-zinc-800 text-zinc-500 border border-white/5 text-[10px]">
              {total - active} reversed
            </Badge>
          )}
        </h4>
      </div>
      <div className="space-y-2">
        {events.map((event) => (
          <MergeEventRow
            key={event.id}
            event={event}
            onReverse={handleReverse}
            pending={pending}
          />
        ))}
      </div>
    </div>
  );
}
