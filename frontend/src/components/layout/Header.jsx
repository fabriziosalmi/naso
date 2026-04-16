import React from 'react';
import { Crosshair, Bell } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useLocation } from 'react-router-dom';

export default function Header({ systemStatus, onOpenNotifications }) {
  const location = useLocation();
  const getPageTitle = () => {
    switch (location.pathname) {
      case '/': return 'Dashboard';
      case '/topology': return 'Neural Topology';
      case '/identities': return 'Master Identities';
      case '/dark-search': return 'Dark Recon Probe';
      case '/audit': return 'Audit & Compliance';
      case '/ai-analyst': return 'AI Co-Analyst';
      case '/docs': return 'Docs & Help';
      default: return 'NASO Engine';
    }
  };

  return (
    <header className="h-16 border-b border-white/[0.08] bg-[#1C1C1E]/50 backdrop-blur-xl flex items-center justify-between px-6 z-30 shrink-0">
          <div className="flex items-center gap-8">
            <div className="flex flex-col">
              <h2 className="text-[14px] font-semibold text-white tracking-tight flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-blue-500 flex items-center justify-center shadow-md">
                    <Crosshair size={12} className="text-white" strokeWidth={2.5} />
                </div>
                {getPageTitle()}
              </h2>
            </div>
            
            <div className="hidden lg:flex items-center gap-5 px-3 py-1 bg-black/40 rounded-full border border-white/5">
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-medium text-zinc-500">Latency</span>
                <span className="text-[11px] font-medium text-zinc-300">{systemStatus?.latency_ms?.total || '0.42'}ms</span>
              </div>
              <div className="w-[1px] h-3 bg-zinc-800"></div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-medium text-zinc-500">Cluster</span>
                <span className="text-[11px] font-medium text-[#0A84FF]">#Alfa-7</span>
              </div>
              <div className="w-[1px] h-3 bg-zinc-800"></div>
              <div className="flex items-center gap-1.5 px-1 py-0.5 rounded-full bg-[#32D74B]/10">
                <div className="w-1.5 h-1.5 bg-[#32D74B] rounded-full"></div>
                <span className="text-[10px] font-semibold text-[#32D74B]">Operational</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button 
              variant="outline" 
              size="icon" 
              onClick={onOpenNotifications}
              className="h-8 w-8 relative border-transparent bg-white/5 text-zinc-300 hover:text-white hover:bg-white/10 rounded-full transition-all"
            >
              <Bell size={14} strokeWidth={2} />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#0A84FF] rounded-full"></span>
            </Button>
            <Button className="h-8 px-4 text-[12px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
                Deploy Unit
            </Button>
          </div>
        </header>
  );
}
