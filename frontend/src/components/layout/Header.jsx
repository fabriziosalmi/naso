import React, { useEffect, useRef, useState } from 'react';
import { Crosshair, Bell, Menu, Search, WifiOff } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useLocation } from 'react-router-dom';
import useNasoStore from '@/store/useNasoStore';

export default function Header({ systemStatus, onOpenNotifications, onOpenSidebar, onOpenCommandMenu, online = true }) {
  const location = useLocation();
  const leaks = useNasoStore((s) => s.leaks);
  const unacknowledged = leaks.filter(l => l.severity_score >= 80 && !l.acknowledged_at).length;

  // Signature pulse: when a new critical alert arrives, the bell briefly pulses.
  const prevCountRef = useRef(unacknowledged);
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    if (unacknowledged > prevCountRef.current) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 1700);
      prevCountRef.current = unacknowledged;
      return () => clearTimeout(t);
    }
    prevCountRef.current = unacknowledged;
  }, [unacknowledged]);

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/': return 'Dashboard';
      case '/topology': return 'Neural Topology';
      case '/identities': return 'Master Identities';
      case '/dark-search': return 'Dark Recon Probe';
      case '/audit': return 'Audit & Compliance';
      case '/ai-analyst': return 'AI Co-Analyst';
      case '/docs': return 'Docs & Help';
      default: return 'NASO';
    }
  };

  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform);

  return (
    <header className="h-16 glass-panel border-b border-t-0 border-l-0 border-r-0 flex items-center justify-between px-4 sm:px-6 z-30 shrink-0 sticky top-0 w-full overflow-hidden">
          <div className="ambient-glow opacity-20"></div>
          <div className="flex items-center gap-3 sm:gap-6 min-w-0">
            {/* Mobile menu button */}
            <button
              onClick={onOpenSidebar}
              aria-label="Open navigation"
              className="lg:hidden p-2 -ml-2 rounded-lg text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
            >
              <Menu size={18} strokeWidth={2} />
            </button>

            <div className="flex flex-col min-w-0">
              <h2 className="text-[14px] font-semibold text-white tracking-tight flex items-center gap-2 truncate">
                <div className="w-6 h-6 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shadow-[0_0_10px_rgba(59,130,246,0.3)] shrink-0">
                    <Crosshair size={12} className="text-blue-400" strokeWidth={2.5} />
                </div>
                {getPageTitle()}
              </h2>
            </div>

            <div className="hidden lg:flex items-center gap-5 px-3 py-1 bg-black/40 rounded-full border border-white/5">
              {/* A measurement or nothing. The fallback here was the literal
                  string '0.42', so a stack that had never answered a probe
                  displayed a plausible database latency to three significant
                  figures. */}
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-medium text-zinc-500">DB latency</span>
                <span className="text-[11px] font-medium text-zinc-300">
                  {typeof systemStatus?.latency_ms?.total === 'number' && systemStatus.latency_ms.total >= 0
                    ? `${systemStatus.latency_ms.total}ms`
                    : '—'}
                </span>
              </div>
              {/* "Cluster #Alfa-7" was a fixed string. NASO has no cluster
                  concept and no node called Alfa-7; it was set dressing in the
                  one strip of the interface a reader takes for instrumentation. */}
              <div className="w-[1px] h-3 bg-zinc-800"></div>
              {online ? (
                <div className="flex items-center gap-1.5 px-1 py-0.5 rounded-full bg-[#32D74B]/10">
                  <div className="w-1.5 h-1.5 bg-[#32D74B] rounded-full"></div>
                  <span className="text-[10px] font-semibold text-[#32D74B] animate-pulse">Operational</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-full bg-[#FFD60A]/10">
                  <WifiOff size={10} className="text-[#FFD60A]" strokeWidth={2.2} />
                  <span className="text-[10px] font-semibold text-[#FFD60A]">Offline · cached</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Global search launcher — opens the command menu */}
            <button
              onClick={onOpenCommandMenu}
              aria-label="Open command menu"
              data-tour="command-palette"
              className="hidden sm:flex items-center gap-2 h-8 pl-2.5 pr-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-zinc-400 hover:text-white hover:bg-white/[0.08] hover:border-white/[0.10] transition-all text-[12px]"
            >
              <Search size={13} strokeWidth={1.8} />
              <span className="hidden md:inline">Search</span>
              <kbd className="inline-flex items-center justify-center h-5 px-1.5 rounded bg-black/40 border border-white/5 text-[10px] font-medium text-zinc-500 font-mono">
                {isMac ? '⌘' : 'Ctrl'}K
              </kbd>
            </button>

            <Button
              variant="outline"
              size="icon"
              onClick={onOpenNotifications}
              aria-label={unacknowledged > 0 ? `Notifications, ${unacknowledged} unacknowledged` : 'Notifications'}
              data-tour="alerts-trigger"
              className={`h-8 w-8 relative border-transparent bg-white/5 text-zinc-300 hover:text-white hover:bg-white/10 rounded-full transition-all ${pulse ? 'signature-pulse' : ''}`}
            >
              <Bell size={14} strokeWidth={2} />
              {unacknowledged > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-4 bg-[#FF453A] text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1 shadow-sm">
                  {unacknowledged > 9 ? '9+' : unacknowledged}
                </span>
              )}
            </Button>
            <Button className="hidden sm:inline-flex h-8 px-4 text-[12px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
                Deploy Unit
            </Button>
          </div>
        </header>
  );
}
