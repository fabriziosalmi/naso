import React, { useMemo } from 'react';
import { Flame, TrendingUp, ShieldAlert, Moon, Activity } from 'lucide-react';

/**
 * Compute insights from current leaks/identities state. Each insight is a
 * small, actionable observation surfaced as a chip above the dashboard KPIs.
 * Insights are intentionally cheap to compute (O(n) over current leaks).
 */
function computeInsights(leaks = [], identities = []) {
  const now = Date.now();
  const HOUR = 3_600_000;
  const DAY = 86_400_000;

  const withTs = leaks
    .map(l => ({ ...l, _ts: new Date(l.discovered_at).getTime() }))
    .filter(l => Number.isFinite(l._ts));

  const out = [];

  // 1. Hot streak — criticals in last hour (threshold ≥2 for interest)
  const lastHourCritical = withTs.filter(l => l.severity_score >= 80 && now - l._ts < HOUR).length;
  if (lastHourCritical >= 2) {
    out.push({
      id: 'hot-streak',
      icon: Flame,
      tone: 'red',
      label: 'Hot streak',
      value: `${lastHourCritical} critical in last 60 min`,
      action: { label: 'Triage', event: 'naso:open-notifications' },
    });
  }

  // 2. Source spike — top source last 7d vs prior 7d
  const bySource = {};
  withTs.forEach(l => {
    const src = (l.source || '').split(':')[0] || 'unknown';
    const bucket = now - l._ts < 7 * DAY ? 'recent' : (now - l._ts < 14 * DAY ? 'prior' : 'old');
    if (bucket === 'old') return;
    bySource[src] ??= { recent: 0, prior: 0 };
    bySource[src][bucket] += 1;
  });
  const spikes = Object.entries(bySource)
    .map(([src, c]) => {
      const prior = c.prior || 0;
      const recent = c.recent || 0;
      if (recent < 3) return null;
      if (prior === 0) return { src, recent, pct: 100 };
      const pct = Math.round(((recent - prior) / prior) * 100);
      return { src, recent, pct };
    })
    .filter(Boolean)
    .sort((a, b) => b.pct - a.pct);
  const topSpike = spikes[0];
  if (topSpike && topSpike.pct >= 40) {
    out.push({
      id: 'source-spike',
      icon: TrendingUp,
      tone: 'orange',
      label: 'Source surge',
      value: `${topSpike.src} ${topSpike.pct > 0 ? '+' : ''}${topSpike.pct}% vs prior 7d`,
    });
  }

  // 3. Unacknowledged backlog — criticals unack older than 6h
  const staleCritical = withTs.filter(
    l => l.severity_score >= 80 && !l.acknowledged_at && now - l._ts > 6 * HOUR
  ).length;
  if (staleCritical >= 1) {
    out.push({
      id: 'stale-critical',
      icon: ShieldAlert,
      tone: 'red',
      label: 'Stale critical',
      value: `${staleCritical} unack > 6h`,
      action: { label: 'Resolve', event: 'naso:open-notifications' },
    });
  }

  // 4. Silent perimeter — zero events in last 24h but data exists overall
  const last24 = withTs.filter(l => now - l._ts < DAY).length;
  if (withTs.length > 0 && last24 === 0) {
    out.push({
      id: 'silent',
      icon: Moon,
      tone: 'blue',
      label: 'Silent perimeter',
      value: 'No events in the last 24h',
    });
  }

  // 5. VIP at risk — any protected identity with risk ≥ 70
  const vipAtRisk = identities.filter(i => i.is_protected && (i.risk_score ?? 0) >= 70);
  if (vipAtRisk.length > 0) {
    out.push({
      id: 'vip-risk',
      icon: ShieldAlert,
      tone: 'yellow',
      label: 'VIP at risk',
      value: `${vipAtRisk.length} protected asset${vipAtRisk.length === 1 ? '' : 's'} ≥ 70`,
    });
  }

  // 6. Ingestion velocity — events per hour in last 6h (baseline insight)
  const last6h = withTs.filter(l => now - l._ts < 6 * HOUR).length;
  if (last6h >= 6) {
    out.push({
      id: 'velocity',
      icon: Activity,
      tone: 'green',
      label: 'Ingestion velocity',
      value: `${(last6h / 6).toFixed(1)} events/hour (6h avg)`,
    });
  }

  return out;
}

const TONE = {
  red:    { text: 'text-[#FF453A]', bg: 'bg-[#FF453A]/10', border: 'border-[#FF453A]/20' },
  orange: { text: 'text-[#FF9F0A]', bg: 'bg-[#FF9F0A]/10', border: 'border-[#FF9F0A]/20' },
  yellow: { text: 'text-[#FFD60A]', bg: 'bg-[#FFD60A]/10', border: 'border-[#FFD60A]/20' },
  blue:   { text: 'text-[#0A84FF]', bg: 'bg-[#0A84FF]/10', border: 'border-[#0A84FF]/20' },
  green:  { text: 'text-[#32D74B]', bg: 'bg-[#32D74B]/10', border: 'border-[#32D74B]/20' },
};

function Chip({ insight }) {
  const Icon = insight.icon;
  const t = TONE[insight.tone] ?? TONE.blue;
  return (
    <div className={`shrink-0 flex items-center gap-3 pl-3 pr-4 h-11 rounded-full border ${t.border} ${t.bg} backdrop-blur-xl`}>
      <div className={`w-7 h-7 rounded-full border ${t.border} flex items-center justify-center bg-black/30`}>
        <Icon size={13} className={t.text} strokeWidth={2} />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">{insight.label}</span>
        <span className="text-[12px] font-medium text-white truncate max-w-[260px]">{insight.value}</span>
      </div>
      {insight.action && (
        <button
          onClick={() => insight.action.event && window.dispatchEvent(new CustomEvent(insight.action.event))}
          className={`ml-2 h-7 px-3 rounded-full border ${t.border} ${t.text} text-[11px] font-medium hover:bg-white/[0.05] transition-colors`}
        >
          {insight.action.label}
        </button>
      )}
    </div>
  );
}

export default function InsightStrip({ leaks, identities }) {
  const insights = useMemo(() => computeInsights(leaks, identities), [leaks, identities]);
  if (insights.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="Real-time intelligence insights"
      data-tour="insights"
      className="flex gap-2 overflow-x-auto scrollbar-hide -mx-1 px-1 pb-1"
    >
      {insights.map(i => <Chip key={i.id} insight={i} />)}
    </div>
  );
}
