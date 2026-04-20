import React, { useEffect, useState, useMemo } from 'react';
import { Command } from 'cmdk';
import {
  Search, Compass, Book, ShieldAlert, Cpu, UserPlus, LayoutDashboard,
  Fingerprint, Flame, ScrollText, Zap, Download, BellOff, Brain, Workflow,
  Database, Globe, Code2, MessageSquare
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import useNasoStore from '@/store/useNasoStore';

export default function CommandMenu() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const identities = useNasoStore(s => s.identities);
  const leaks = useNasoStore(s => s.leaks);
  const auditLogs = useNasoStore(s => s.auditLogs);
  const fetchIdentityInsights = useNasoStore(s => s.fetchIdentityInsights);
  const acknowledgeAllLeaks = useNasoStore(s => s.acknowledgeAllLeaks);
  const exportMassiveDossier = useNasoStore(s => s.exportMassiveDossier);
  const triggerIdentityMerging = useNasoStore(s => s.triggerIdentityMerging);
  const fetchAuditLogs = useNasoStore(s => s.fetchAuditLogs);

  useEffect(() => {
    const down = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(v => !v);
      }
    };
    const openHandler = () => setOpen(true);
    document.addEventListener('keydown', down);
    window.addEventListener('naso:open-command', openHandler);
    return () => {
      document.removeEventListener('keydown', down);
      window.removeEventListener('naso:open-command', openHandler);
    };
  }, []);

  // When the palette opens, prefetch audit logs once — cheap, enables
  // full-text search across actions/payloads without a mandatory visit.
  useEffect(() => {
    if (open && auditLogs.length === 0) fetchAuditLogs();
  }, [open]); // eslint-disable-line

  const [query, setQuery] = useState('');
  const close = () => { setOpen(false); setQuery(''); };
  const go = (path) => { close(); navigate(path); };

  // Leak ranking: when no query, surface unack criticals first; when there's
  // a query, cmdk's built-in fuzzy matching handles it via the keywords prop
  // on each item — we just expose a bounded slice so the palette stays fast.
  const rankedLeaks = useMemo(() => {
    if (!leaks?.length) return [];
    const withScore = leaks.map(l => {
      const isUnackCrit = l.severity_score >= 80 && !l.acknowledged_at;
      return { leak: l, score: (isUnackCrit ? 1000 : 0) + (l.severity_score ?? 0) };
    });
    withScore.sort((a, b) => b.score - a.score);
    return withScore.slice(0, 20).map(x => x.leak);
  }, [leaks]);

  // Audit: most recent 30 events, since it's full-text searchable via cmdk.
  const recentAudit = useMemo(() => {
    if (!auditLogs?.length) return [];
    return [...auditLogs]
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .slice(0, 30);
  }, [auditLogs]);

  const sourceIcon = (source = '') => {
    const s = source.toLowerCase();
    if (s.includes('github'))  return Code2;
    if (s.includes('telegram')) return MessageSquare;
    if (s.includes('dark'))     return ShieldAlert;
    return Globe;
  };

  const severityTone = (score) =>
    score >= 80 ? 'text-[#FF453A]' :
    score >= 50 ? 'text-[#FF9F0A]' :
    'text-[#32D74B]';

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-start justify-center pt-[15vh] px-4"
      onClick={close}
    >
      <div
        className="w-[620px] max-w-full bg-[#18181b]/95 backdrop-blur-2xl border border-white/[0.08] shadow-2xl rounded-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <Command
          label="Global Command Menu"
          shouldFilter
          onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); close(); } }}
        >
          <div className="flex items-center border-b border-white/[0.08] px-4">
             <Search className="w-4 h-4 text-zinc-500 mr-3" strokeWidth={1.8} />
             <Command.Input
                autoFocus
                value={query}
                onValueChange={setQuery}
                placeholder="Search navigation, identities, leaks, audit events…"
                className="w-full bg-transparent outline-none h-14 text-white text-[14px] placeholder:text-zinc-500"
             />
             <kbd className="hidden sm:inline-flex items-center justify-center h-6 px-2 rounded bg-zinc-800 text-zinc-400 text-[10px] font-mono font-medium">
                ESC
             </kbd>
          </div>

          <Command.List className="max-h-[440px] overflow-y-auto p-2 scrollbar-thin text-[14px]">
            <Command.Empty className="py-10 text-center text-zinc-500 text-[12px]">
              <div className="flex flex-col items-center gap-2">
                <Search size={20} strokeWidth={1.2} className="text-zinc-700" />
                <span>No results. Try another keyword.</span>
              </div>
            </Command.Empty>

            <Command.Group heading="Navigation" className="text-[10px] uppercase tracking-wider font-medium text-zinc-500 px-2 pt-2 pb-1">
              <Item icon={LayoutDashboard} onSelect={() => go('/')}>Dashboard</Item>
              <Item icon={Compass} onSelect={() => go('/topology')}>Open Topology Matrix</Item>
              <Item icon={Fingerprint} onSelect={() => go('/identities')}>Master Identities</Item>
              <Item icon={Flame} onSelect={() => go('/dark-search')}>Dark Recon Probe</Item>
              <Item icon={ScrollText} onSelect={() => go('/audit')}>Audit &amp; Compliance</Item>
              <Item icon={Brain} onSelect={() => go('/ai-analyst')}>Consult AI Co-Analyst</Item>
              <Item icon={Book} onSelect={() => go('/docs')}>Security Operations Manual</Item>
            </Command.Group>

            <Command.Group heading="Quick actions" className="text-[10px] uppercase tracking-wider font-medium text-zinc-500 px-2 pt-3 pb-1">
              <Item icon={UserPlus} onSelect={() => { close(); window.dispatchEvent(new CustomEvent('naso:add-identity')); }}>
                Register new identity…
              </Item>
              <Item icon={Workflow} onSelect={() => { close(); triggerIdentityMerging(); }}>
                Run auto-merge across identities
              </Item>
              <Item icon={BellOff} onSelect={() => { close(); acknowledgeAllLeaks(); }}>
                Acknowledge all critical alerts
              </Item>
              <Item icon={Download} onSelect={() => { close(); exportMassiveDossier(); }}>
                Export full forensic dossier
              </Item>
            </Command.Group>

            {identities.length > 0 && (
              <Command.Group heading="Identities" className="text-[10px] uppercase tracking-wider font-medium text-zinc-500 px-2 pt-3 pb-1">
                {identities.slice(0, 8).map((id) => (
                  <Item
                    key={id.id}
                    icon={Fingerprint}
                    iconClass={id.is_protected ? 'text-[#FFD60A]' : 'text-[#0A84FF]'}
                    keywords={[id.identifier, id.type]}
                    onSelect={() => { close(); fetchIdentityInsights(id.id); }}
                  >
                    <span className="flex-1 truncate">{id.identifier}</span>
                    <span className="ml-auto text-[10px] text-zinc-600 font-mono">
                      risk {id.risk_score ?? 0}
                    </span>
                  </Item>
                ))}
              </Command.Group>
            )}

            {rankedLeaks.length > 0 && (
              <Command.Group heading={query ? 'Leaks' : 'Top leaks'} className="text-[10px] uppercase tracking-wider font-medium text-zinc-500 px-2 pt-3 pb-1">
                {rankedLeaks.map((leak) => {
                  const SrcIcon = sourceIcon(leak.source);
                  const unackCrit = leak.severity_score >= 80 && !leak.acknowledged_at;
                  return (
                    <Item
                      key={leak.id}
                      icon={unackCrit ? ShieldAlert : SrcIcon}
                      iconClass={unackCrit ? 'text-[#FF453A]' : 'text-zinc-400'}
                      keywords={[
                        leak.source ?? '',
                        leak.content_snippet ?? '',
                        leak.id?.slice(0, 8) ?? '',
                        String(leak.severity_score ?? ''),
                        unackCrit ? 'critical unacknowledged' : '',
                      ]}
                      onSelect={() => { close(); go('/'); }}
                    >
                      <span className="flex-1 min-w-0">
                        <span className="block text-[12px] text-white truncate">{leak.source || '—'}</span>
                        {leak.content_snippet && (
                          <span className="block text-[10px] text-zinc-500 truncate font-mono">
                            {leak.content_snippet.slice(0, 80)}
                          </span>
                        )}
                      </span>
                      <span className={`ml-auto text-[10px] font-mono ${severityTone(leak.severity_score ?? 0)}`}>
                        {leak.severity_score ?? 0}
                      </span>
                    </Item>
                  );
                })}
              </Command.Group>
            )}

            {recentAudit.length > 0 && (
              <Command.Group heading={query ? 'Audit events' : 'Recent audit'} className="text-[10px] uppercase tracking-wider font-medium text-zinc-500 px-2 pt-3 pb-1">
                {recentAudit.map((log) => (
                  <Item
                    key={log.id}
                    icon={ScrollText}
                    iconClass="text-zinc-500"
                    keywords={[
                      log.action ?? '',
                      log.user_id ?? '',
                      log.resource_type ?? '',
                      log.details ? JSON.stringify(log.details) : '',
                    ]}
                    onSelect={() => { close(); go('/audit'); }}
                  >
                    <span className="flex-1 min-w-0">
                      <span className="block text-[12px] text-white truncate">{log.action?.replace(/_/g, ' ') || '—'}</span>
                      <span className="block text-[10px] text-zinc-500 truncate font-mono">
                        {log.resource_type || 'system'} · {log.user_id?.slice(0, 8) || 'unknown'}
                      </span>
                    </span>
                    <span className="ml-auto text-[9px] text-zinc-600 font-mono whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleDateString()}
                    </span>
                  </Item>
                ))}
              </Command.Group>
            )}
          </Command.List>

          <div className="border-t border-white/[0.06] px-3 py-2 flex items-center justify-between text-[10px] text-zinc-500">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1"><KbdKey>↑</KbdKey><KbdKey>↓</KbdKey> navigate</span>
              <span className="flex items-center gap-1"><KbdKey>↵</KbdKey> select</span>
              <span className="flex items-center gap-1"><KbdKey>esc</KbdKey> close</span>
            </div>
            <span className="flex items-center gap-1.5">
              <Zap size={10} className="text-[#0A84FF]" strokeWidth={2} /> NASO Command
            </span>
          </div>
        </Command>
      </div>
    </div>
  );
}

function Item({ icon: Icon, iconClass, onSelect, children, keywords }) {
  return (
    <Command.Item
      onSelect={onSelect}
      keywords={keywords}
      className="flex items-center gap-3 px-3 py-2 my-0.5 rounded-lg text-[13px] text-zinc-300 cursor-pointer aria-selected:bg-white/[0.06] aria-selected:text-white transition-colors"
    >
      {Icon && <Icon className={`w-4 h-4 ${iconClass ?? 'text-zinc-400'}`} strokeWidth={1.8} />}
      {children}
    </Command.Item>
  );
}

function KbdKey({ children }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded bg-black/40 border border-white/5 text-[10px] font-mono text-zinc-400">
      {children}
    </kbd>
  );
}
