import React, { useEffect, useMemo, useState } from 'react';
import useNasoStore from '@/store/useNasoStore';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { GitMerge, ShieldAlert, Loader2, Sparkles, RefreshCw } from 'lucide-react';

// Default-on threshold: confidence at or above this ticks the pair on
// open. Matches the operator mental model of "trust the strong
// candidates, inspect the borderline ones".
const AUTO_SELECT_CONFIDENCE = 0.75;

function ConfidenceBar({ value }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone =
    value >= 0.85 ? 'bg-[#32D74B]' :
    value >= 0.65 ? 'bg-[#FFD60A]' :
    'bg-[#FF9F0A]';
  return (
    <div className="w-20 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
      <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function PairRow({ pair, checked, onToggle }) {
  const m = pair.master;
  const s = pair.slave;
  return (
    <label
      className={`group flex items-start gap-3 p-3 rounded-xl border transition-colors cursor-pointer ${
        checked
          ? 'bg-[#0A84FF]/[0.06] border-[#0A84FF]/30'
          : 'bg-black/30 border-white/[0.06] hover:border-white/[0.10]'
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        aria-label={`Select merge ${s.identifier} under ${m.identifier}`}
        className="mt-1 accent-[#0A84FF]"
      />
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[12px] text-white truncate">{m.identifier}</span>
          {m.is_protected && <Badge className="bg-[#FFD60A]/10 text-[#FFD60A] border-[#FFD60A]/20 text-[9px]">VIP</Badge>}
          <span className="text-zinc-600 text-[10px]">←</span>
          <span className="font-mono text-[12px] text-zinc-400 truncate">{s.identifier}</span>
          {s.is_protected && <Badge className="bg-[#FFD60A]/10 text-[#FFD60A] border-[#FFD60A]/20 text-[9px]">VIP</Badge>}
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <div className="flex items-center gap-2">
            <ConfidenceBar value={pair.confidence} />
            <span className="text-zinc-500 font-mono tabular-nums w-10">{pair.confidence.toFixed(2)}</span>
          </div>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-500">
            {pair.shared_leak_count} shared leak{pair.shared_leak_count === 1 ? '' : 's'}
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-zinc-500">
            risk {m.risk_score} vs {s.risk_score}
          </span>
        </div>
      </div>
    </label>
  );
}

export default function MergePreviewDrawer() {
  const open = useNasoStore(s => s.mergePreviewDrawerOpen);
  const close = useNasoStore(s => s.closeMergePreviewDrawer);
  const preview = useNasoStore(s => s.mergePreview);
  const fetchMergePreview = useNasoStore(s => s.fetchMergePreview);
  const executeSelectedMerges = useNasoStore(s => s.executeSelectedMerges);

  // selection is keyed on `${master_id}:${slave_id}` for stable lookup
  // regardless of pair reordering when the preview is refetched.
  const [selected, setSelected] = useState(new Set());
  const [executing, setExecuting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const pairs = preview?.pairs ?? [];

  // When the preview first arrives (or is refetched) auto-select every
  // pair above the high-confidence threshold. The operator can still
  // un-tick individual rows before executing.
  useEffect(() => {
    if (!preview) return;
    const initial = new Set();
    pairs.forEach(p => {
      if (p.confidence >= AUTO_SELECT_CONFIDENCE) {
        initial.add(`${p.master.id}:${p.slave.id}`);
      }
    });
    setSelected(initial);
  }, [preview?.count]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (p) => {
    const key = `${p.master.id}:${p.slave.id}`;
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const handleExecute = async () => {
    const toExecute = pairs
      .filter(p => selected.has(`${p.master.id}:${p.slave.id}`))
      .map(p => ({ master_id: p.master.id, slave_id: p.slave.id }));
    if (!toExecute.length) return;
    setExecuting(true);
    try {
      await executeSelectedMerges(toExecute);
      setSelected(new Set()); // clear; the refresh will repopulate from new preview
    } finally {
      setExecuting(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetchMergePreview();
    } finally {
      setRefreshing(false);
    }
  };

  const selectedCount = selected.size;

  return (
    <Sheet open={open} onOpenChange={(o) => (o ? null : close())}>
      <SheetContent
        side="right"
        className="w-[480px] sm:w-[540px] max-w-full bg-[#1C1C1E]/95 backdrop-blur-3xl border-l border-white/[0.08] p-0 shadow-2xl flex flex-col"
      >
        <SheetHeader className="p-6 border-b border-white/[0.08]">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-[17px] font-semibold tracking-tight text-white flex items-center gap-3">
              <div className="p-1.5 bg-[#0A84FF]/10 rounded-lg">
                <GitMerge className="text-[#0A84FF]" size={16} strokeWidth={1.5} />
              </div>
              Merge candidates
            </SheetTitle>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              aria-label="Refresh preview"
              className="h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors disabled:opacity-40"
            >
              {refreshing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            </button>
          </div>
          <SheetDescription className="text-[12px] text-zinc-500 mt-1">
            Evidence-gated pairs that share at least one leak. Tick the ones you want to merge — the auto-selector pre-ticks everything at confidence ≥ {AUTO_SELECT_CONFIDENCE}.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-5 space-y-2 scrollbar-hide">
          {!preview ? (
            <div className="h-48 flex flex-col items-center justify-center text-zinc-600 gap-3">
              <Loader2 size={20} className="animate-spin" />
              <p className="text-[12px]">Computing candidates…</p>
            </div>
          ) : pairs.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-zinc-600 gap-4 text-center">
              <ShieldAlert size={28} strokeWidth={1.2} />
              <div>
                <p className="text-[13px] font-medium text-zinc-400">No merge candidates</p>
                <p className="text-[11px] text-zinc-500 mt-1 max-w-xs">
                  No pairs of identities currently share any leaks. Ingest more sources or adjust the confidence threshold.
                </p>
              </div>
            </div>
          ) : (
            pairs.map(p => (
              <PairRow
                key={`${p.master.id}:${p.slave.id}`}
                pair={p}
                checked={selected.has(`${p.master.id}:${p.slave.id}`)}
                onToggle={() => toggle(p)}
              />
            ))
          )}
        </div>

        <div className="p-5 border-t border-white/[0.08] flex items-center justify-between gap-3">
          <div className="text-[11px] text-zinc-500">
            {selectedCount}/{pairs.length} selected
            {pairs.length > 0 && selectedCount > 0 && (
              <span className="ml-2 text-[#0A84FF] inline-flex items-center gap-1">
                <Sparkles size={10} strokeWidth={2} /> ready to commit
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              onClick={close}
              className="h-9 px-4 text-[13px] text-zinc-400 hover:text-white rounded-full"
            >
              Cancel
            </Button>
            <Button
              onClick={handleExecute}
              disabled={executing || selectedCount === 0}
              className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm"
            >
              {executing
                ? <Loader2 size={14} className="animate-spin" />
                : selectedCount > 0
                  ? `Merge ${selectedCount} pair${selectedCount === 1 ? '' : 's'}`
                  : 'Merge selected'
              }
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
