import React, { useMemo, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ShieldAlert, ShieldCheck, Zap, Filter } from 'lucide-react';

const FILTERS = [
  { value: 'critical', label: 'Critical', min: 80 },
  { value: 'high', label: 'High', min: 50 },
  { value: 'all', label: 'All', min: 0 },
];

function bucketOf(ts) {
  const d = new Date(ts).getTime();
  if (!Number.isFinite(d)) return 'Older';
  const now = Date.now();
  const diff = now - d;
  if (diff < 3_600_000) return 'Last hour';
  if (diff < 86_400_000) return 'Today';
  if (diff < 172_800_000) return 'Yesterday';
  if (diff < 604_800_000) return 'This week';
  return 'Older';
}

const BUCKET_ORDER = ['Last hour', 'Today', 'Yesterday', 'This week', 'Older'];

function NotificationItem({ alert, onAck }) {
  return (
    <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all cursor-pointer relative overflow-hidden">
      <div className="flex gap-4">
        <div className={`p-2 rounded-lg ${alert.severity_score >= 80 ? 'bg-red-500/10 text-red-500' : 'bg-blue-500/10 text-blue-500'}`}>
          {alert.severity_score >= 80 ? <ShieldAlert size={16} /> : <Zap size={16} />}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex justify-between items-start">
            <p className={`text-xs font-semibold ${alert.severity_score >= 80 ? 'text-red-400' : 'text-blue-400'}`}>
              {alert.severity_score >= 80 ? 'Critical Breach' : 'Intelligence Match'}
            </p>
            {alert.acknowledged_at ? (
              <span className="text-[10px] text-zinc-600">Acknowledged</span>
            ) : (
              <span className="text-[10px] text-zinc-500">{new Date(alert.discovered_at).toLocaleTimeString()}</span>
            )}
          </div>
          <p className="text-xs text-zinc-400">
            Artifact identified from <span className="text-zinc-200 font-medium">{alert.source}</span>.
          </p>
        </div>
      </div>
      {!alert.acknowledged_at && (
        <button
          onClick={(e) => { e.stopPropagation(); onAck(alert.id); }}
          className="mt-2 w-full py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-[11px] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-all text-center"
        >
          Acknowledge
        </button>
      )}
    </div>
  );
}

export default function NotificationsSheet({ open, onOpenChange, leaks, acknowledgeLeak, acknowledgeAllLeaks }) {
  const [severity, setSeverity] = useState('critical');

  const min = FILTERS.find(f => f.value === severity)?.min ?? 80;
  const unacknowledgedCount = leaks.filter(l => l.severity_score >= 80 && !l.acknowledged_at).length;

  const grouped = useMemo(() => {
    const list = leaks.filter(l => l.severity_score >= min);
    const byBucket = new Map();
    BUCKET_ORDER.forEach(b => byBucket.set(b, []));
    list.forEach(a => {
      const b = bucketOf(a.discovered_at);
      byBucket.get(b).push(a);
    });
    // Sort each bucket newest-first
    byBucket.forEach(arr => arr.sort((a, b) => new Date(b.discovered_at) - new Date(a.discovered_at)));
    return Array.from(byBucket.entries()).filter(([, arr]) => arr.length > 0);
  }, [leaks, min]);

  const isEmpty = grouped.length === 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[400px] sm:w-[480px] bg-[#1C1C1E]/95 backdrop-blur-3xl border-l border-white/[0.08] p-0 shadow-2xl flex flex-col">
        <SheetHeader className="p-6 border-b border-white/[0.08]">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-[17px] font-semibold tracking-tight text-white flex items-center gap-3">
              <div className="p-1.5 bg-[#FF453A]/10 rounded-lg"><Zap className="text-[#FF453A]" size={16} strokeWidth={1.5} /></div>
              Intelligence Alerts
            </SheetTitle>
            <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-[#FF453A]/10">
              <div className="w-1.5 h-1.5 rounded-full bg-[#FF453A] animate-pulse"></div>
              <span className="text-[11px] font-medium text-[#FF453A]">Live</span>
            </div>
          </div>
          <SheetDescription className="text-[12px] text-zinc-500 mt-1">
            {unacknowledgedCount > 0
              ? `${unacknowledgedCount} critical alert${unacknowledgedCount === 1 ? '' : 's'} pending acknowledgement.`
              : 'All critical alerts acknowledged. Perimeter green.'}
          </SheetDescription>

          {/* Severity filter segmented control */}
          <div className="mt-4 inline-flex items-center gap-1 p-1 rounded-full bg-black/40 border border-white/[0.06]" role="tablist" aria-label="Severity filter">
            {FILTERS.map(f => (
              <button
                key={f.value}
                role="tab"
                aria-selected={severity === f.value}
                onClick={() => setSeverity(f.value)}
                className={`flex items-center gap-1.5 h-7 px-3 rounded-full text-[11px] font-medium transition-colors ${
                  severity === f.value
                    ? 'bg-white/[0.08] text-white shadow-sm'
                    : 'text-zinc-500 hover:text-white'
                }`}
              >
                <Filter size={10} strokeWidth={1.8} />
                {f.label}
              </button>
            ))}
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-5 space-y-6 scrollbar-hide">
          {grouped.map(([bucket, items]) => (
            <section key={bucket}>
              <h3 className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-medium mb-2 flex items-center gap-2">
                {bucket}
                <span className="text-zinc-700">·</span>
                <span className="text-zinc-600 font-mono">{items.length}</span>
              </h3>
              <div className="space-y-2">
                {items.map(alert => (
                  <NotificationItem key={alert.id} alert={alert} onAck={acknowledgeLeak} />
                ))}
              </div>
            </section>
          ))}

          {isEmpty && (
            <div className="h-48 flex flex-col items-center justify-center text-zinc-600 gap-4">
              <ShieldCheck size={36} className="text-[#32D74B]" strokeWidth={1.5} />
              <p className="text-[13px] font-medium text-zinc-500">No alerts at this severity</p>
            </div>
          )}
        </div>

        <div className="p-5 border-t border-white/[0.08]">
          <Button
            className="w-full h-10 font-medium text-[13px] bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full"
            onClick={() => acknowledgeAllLeaks()}
            disabled={unacknowledgedCount === 0}
          >
            {unacknowledgedCount > 0
              ? `Mark ${unacknowledgedCount} critical ${unacknowledgedCount === 1 ? 'alert' : 'alerts'} as Resolved`
              : 'All Resolved'}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
