import React, {useState, useEffect} from 'react';
import { NavLink } from 'react-router-dom';
import useNasoStore from '@/store/useNasoStore';
import { 
  Radar, LayoutDashboard, Share2, Fingerprint, Flame, ScrollText, Brain, BookOpen, Settings
} from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TerminalLog } from './TerminalLog';
import * as Tooltip from '@radix-ui/react-tooltip';

export default function Sidebar({ onEditProfile }) {
  const user = useNasoStore((s) => s.user);
  const role = user?.role;
  const [terminalLogs, setTerminalLogs] = useState([]);

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

  const getNavClass = ({ isActive }) => 
    `flex items-center gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium w-full ${isActive ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`;

  return (
    <aside className="w-[260px] glass-panel border-r flex flex-col z-20 shrink-0 relative overflow-hidden">
        <div className="ambient-glow opacity-30"></div>
        <div className="p-6 flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <div className="bg-[#0A84FF] p-2 rounded-xl shadow-[0_0_15px_rgba(10,132,255,0.4)] animate-pulse-glow flex items-center justify-center">
              <img src="/naso-logo.svg" alt="NASO" className="w-[18px] h-[18px] animate-radar" />
            </div>
            <div className="flex flex-col">
              <span className="text-[15px] font-semibold tracking-tight text-white shimmer-text">NASO</span>
              <span className="text-[11px] text-zinc-400 font-medium">Forensic OS v0.1</span>
            </div>
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
        <nav className="flex-1 px-3 space-y-0.5" data-tour="navigation">
          <p className="px-3 py-2 text-[11px] font-medium text-zinc-500 mb-1">Navigation</p>
          
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/" className={getNavClass}><LayoutDashboard size={16} strokeWidth={1.5} /> <span>Dashboard</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 Overview of Active Feeds
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/topology" className={getNavClass} data-tour="topology"><Share2 size={16} strokeWidth={1.5} /> <span>Neural Topology</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 2D Matrix of Threat Correlations
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/identities" className={getNavClass}><Fingerprint size={16} strokeWidth={1.5} /> <span>Master Identities</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 Manage Tracked VIP Assets
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/dark-search" className={getNavClass}><Flame size={16} strokeWidth={1.5} /> <span>Dark Recon Probe</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 Launch Onion Tor Scans
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/audit" className={getNavClass}><ScrollText size={16} strokeWidth={1.5} /> <span>Audit Logs</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 System Security Events
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <div className="pt-2 pb-1">
            <div className="h-[1px] bg-white/[0.05] mx-1" />
            <p className="px-3 pt-3 pb-1 text-[11px] font-medium text-zinc-500">Intelligence</p>
          </div>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/ai-analyst" className={getNavClass} data-tour="ai-analyst"><Brain size={16} strokeWidth={1.5} /> <span>AI Co-Analyst</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 Local LLM Investigation Core
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
               <NavLink to="/docs" className={getNavClass}><BookOpen size={16} strokeWidth={1.5} /> <span>Docs & Help</span></NavLink>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content side="right" sideOffset={10} className="bg-zinc-800 text-white text-xs px-2 py-1 rounded shadow-xl border border-zinc-700 animate-in fade-in zoom-in-95">
                 SOPs & API Documentation
                 <Tooltip.Arrow className="fill-zinc-800" />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </nav>
        </Tooltip.Provider>

        <div className="p-4 mt-auto border-t border-white/[0.08] bg-transparent">
          <TerminalLog logs={terminalLogs} />
          <div className="flex items-center gap-3 mt-4 p-2 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.06] transition-all cursor-pointer">
            <div className="w-8 h-8 rounded-lg bg-[#0A84FF] shadow-sm flex items-center justify-center">
              <span className="text-white font-bold text-xs">{user?.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[13px] font-medium text-white tracking-tight">{user?.full_name || "User"}</span>
              <span className="text-[10px] text-zinc-400">{user?.role || "operator"}</span>
            </div>
            <Button variant="ghost" size="icon" onClick={onEditProfile} className="ml-auto h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10"><Settings size={14} /></Button>
          </div>
        </div>
      </aside>
  );
}
