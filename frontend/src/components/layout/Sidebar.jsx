import React, {useState, useEffect} from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import useNasoStore from '@/store/useNasoStore';
import {
  Radar, LayoutDashboard, Share2, Fingerprint, Flame, ScrollText, Brain, BookOpen, X,
  User, LogOut, Keyboard, HelpCircle, ChevronUp, Compass
} from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { TerminalLog } from './TerminalLog';
import * as Tooltip from '@radix-ui/react-tooltip';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', tip: 'Overview of Active Feeds' },
  { to: '/topology', icon: Share2, label: 'Neural Topology', tip: '2D Matrix of Threat Correlations', tour: 'topology' },
  { to: '/identities', icon: Fingerprint, label: 'Master Identities', tip: 'Manage Tracked VIP Assets' },
  { to: '/dark-search', icon: Flame, label: 'Dark Recon Probe', tip: 'Launch Onion Tor Scans' },
  { to: '/audit', icon: ScrollText, label: 'Audit Logs', tip: 'System Security Events' },
];

const INTEL_ITEMS = [
  { to: '/ai-analyst', icon: Brain, label: 'AI Co-Analyst', tip: 'Local LLM Investigation Core', tour: 'ai-analyst' },
  { to: '/docs', icon: BookOpen, label: 'Docs & Help', tip: 'SOPs & API Documentation' },
];

function NavItem({ item, onNavigate }) {
  const { icon: Icon, to, label, tip, tour } = item;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <NavLink
          to={to}
          end={to === '/'}
          onClick={onNavigate}
          data-tour={tour}
          className={({ isActive }) =>
            `flex flex-nowrap flex-row items-center gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium w-full whitespace-nowrap ${
              isActive ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'
            }`
          }
        >
          <Icon size={16} strokeWidth={1.5} /> <span>{label}</span>
        </NavLink>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={10}
          className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95 hidden lg:block"
        >
          {tip}
          <Tooltip.Arrow className="fill-zinc-800" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export default function Sidebar({ onEditProfile, open, onClose }) {
  const user = useNasoStore((s) => s.user);
  const logout = useNasoStore((s) => s.logout);
  const navigate = useNavigate();
  const role = user?.role;
  const [terminalLogs, setTerminalLogs] = useState([]);

  // Close drawer on ESC (mobile only)
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    const events = [
        "Inbound telemetry from TOR node node_alfa_3",
        "YARA scan complete: 12 matches found",
        "AI Triage initiated for artifact 8f2c3",
        "Identity correlation engine updated MasterProfile: f.salmi",
        "MinIO object storage verified: artifact_01.png",
        "Distributed trace: elasticsearch indexing success",
        "Circuit Breaker [Elasticsearch]: Status CLOSED"
    ];

    const interval = setInterval(() => {
        const newLog = {
            time: new Date().toLocaleTimeString(),
            msg: events[Math.floor(Math.random() * events.length)],
            type: Math.random() > 0.8 ? 'warn' : 'info'
        };
        setTerminalLogs(prev => [...prev.slice(-49), newLog]);
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  return (
    <>
      {/* Mobile backdrop */}
      <div
        onClick={onClose}
        aria-hidden="true"
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden transition-opacity duration-300 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      />

      <aside
        aria-label="Primary navigation"
        className={`w-[260px] glass-panel border-r flex flex-col z-40 shrink-0 overflow-hidden
          fixed lg:static top-0 left-0 h-full transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]
          ${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}
      >
          <div className="ambient-glow opacity-30"></div>
          <div className="p-6 flex flex-col gap-6">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="bg-[#0A84FF] p-2 rounded-xl shadow-[0_0_15px_rgba(10,132,255,0.4)] animate-pulse-glow flex items-center justify-center">
                  <img src="/naso-logo.svg" alt="NASO" className="w-[18px] h-[18px] animate-radar" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[15px] font-semibold tracking-tight text-white shimmer-text">NASO</span>
                  <span className="text-[11px] text-zinc-400 font-medium">Forensic OS v0.1</span>
                </div>
              </div>
              {/* Close on mobile only */}
              <button
                onClick={onClose}
                aria-label="Close navigation"
                className="lg:hidden p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            <div className="bg-white/[0.03] p-3 rounded-xl border border-white/[0.05] space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-medium text-zinc-400">Role</span>
                  <Badge variant="outline" className="text-[10px] h-5 border-white/[0.1] bg-white/[0.02]">{role || "Operator"}</Badge>
              </div>
              <div className="flex justify-between items-center">
                  <span className="text-[11px] font-medium text-zinc-400">Vault</span>
                  <span className="text-[11px] text-[#32D74B] font-medium flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#32D74B]"></div> Active</span>
              </div>
            </div>
          </div>

          <Tooltip.Provider delayDuration={200}>
          <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto scrollbar-hide" data-tour="navigation">
            <p className="px-3 py-2 text-[11px] font-medium text-zinc-500 mb-1">Navigation</p>
            {NAV_ITEMS.map(item => <NavItem key={item.to} item={item} onNavigate={onClose} />)}

            <div className="pt-2 pb-1">
              <div className="h-[1px] bg-white/[0.05] mx-1" />
              <p className="px-3 pt-3 pb-1 text-[11px] font-medium text-zinc-500">Intelligence</p>
            </div>
            {INTEL_ITEMS.map(item => <NavItem key={item.to} item={item} onNavigate={onClose} />)}
          </nav>
          </Tooltip.Provider>

          <div className="p-4 mt-auto border-t border-white/[0.08] bg-transparent hidden xl:block">
            <TerminalLog logs={terminalLogs} />
          </div>
          <div className="p-4 border-t border-white/[0.08] xl:border-0 xl:pt-0">
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  className="w-full flex items-center gap-3 p-2 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.06] transition-all text-left"
                  aria-label="Open user menu"
                  data-tour="user-menu"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#0A84FF] shadow-sm flex items-center justify-center shrink-0">
                    <span className="text-white font-bold text-xs">
                      {user?.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
                    </span>
                  </div>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-[13px] font-medium text-white tracking-tight truncate">{user?.full_name || "User"}</span>
                    <span className="text-[10px] text-zinc-400 truncate">{user?.email || user?.role || "operator"}</span>
                  </div>
                  <ChevronUp size={14} strokeWidth={2} className="text-zinc-500 shrink-0" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  side="top"
                  sideOffset={8}
                  align="start"
                  className="w-[240px] bg-[#1C1C1E]/95 backdrop-blur-2xl border border-white/[0.08] rounded-2xl shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150"
                >
                  <div className="px-3 py-2.5 border-b border-white/[0.04]">
                    <p className="text-[12px] font-semibold text-white truncate">{user?.full_name || "Operator"}</p>
                    <p className="text-[11px] text-zinc-500 truncate">{user?.email || "—"}</p>
                    <div className="mt-1.5 inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06]">
                      <span className="w-1 h-1 rounded-full bg-[#32D74B]" />
                      <span className="text-[10px] text-zinc-400 font-mono uppercase">{role || 'operator'}</span>
                    </div>
                  </div>

                  <MenuItem icon={User} onSelect={onEditProfile}>Edit profile</MenuItem>
                  <MenuItem
                    icon={Keyboard}
                    shortcut="?"
                    onSelect={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))}
                  >
                    Keyboard shortcuts
                  </MenuItem>
                  <MenuItem
                    icon={Compass}
                    onSelect={() => window.dispatchEvent(new CustomEvent('naso:restart-tour'))}
                  >
                    Restart tour
                  </MenuItem>
                  <MenuItem icon={HelpCircle} onSelect={() => navigate('/docs')}>
                    Help &amp; docs
                  </MenuItem>

                  <DropdownMenu.Separator className="h-px bg-white/[0.05] my-1.5" />

                  <MenuItem icon={LogOut} onSelect={logout} destructive>
                    Sign out
                  </MenuItem>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        </aside>
    </>
  );
}

function MenuItem({ icon: Icon, onSelect, children, shortcut, destructive }) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] cursor-pointer outline-none transition-colors ${
        destructive
          ? 'text-[#FF453A] data-[highlighted]:bg-[#FF453A]/10'
          : 'text-zinc-300 data-[highlighted]:bg-white/[0.06] data-[highlighted]:text-white'
      }`}
    >
      {Icon && <Icon size={14} strokeWidth={1.8} className={destructive ? 'text-[#FF453A]' : 'text-zinc-400'} />}
      <span className="flex-1">{children}</span>
      {shortcut && (
        <kbd className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded bg-black/40 border border-white/[0.06] text-[10px] font-mono text-zinc-500">
          {shortcut}
        </kbd>
      )}
    </DropdownMenu.Item>
  );
}
