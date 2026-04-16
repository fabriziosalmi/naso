import React, { useEffect, useState, useMemo, useRef } from 'react';
import useNasoStore from './store/useNasoStore';
import { 
  Shield, 
  AlertTriangle, 
  Search, 
  Users, 
  Activity, 
  FileText,
  Globe,
  MessageSquare,
  Loader2,
  TrendingDown,
  TrendingUp,
  PieChart as PieChartIcon,
  ChevronRight,
  Terminal as TerminalIcon,
  Settings,
  Bell,
  Menu,
  LayoutDashboard,
  ExternalLink,
  History,
  Lock,
  Unlock,
  Filter,
  Download,
  Database,
  Cpu,
  Fingerprint,
  Zap,
  Info,
  Clock,
  Eye,
  Trash2,
  MoreVertical,
  CheckCircle2,
  ShieldCheck,
  AlertOctagon,
  Radio,
  ScrollText,
  Image as ImageIcon,
  Workflow,
  X,
  UserPlus,
  Flame,
  Share2,
  Target,
  Crosshair,
  ShieldAlert,
  Code2,
  Radar
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription 
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import axios from 'axios';
import NetworkGraphPro from './components/NetworkGraph';

// --- Tactical Components ---

// Removed TacticalOverlay completely to provide clean SaaS look
const TacticalOverlay = () => null;

const TerminalLog = ({ logs }) => {
  const scrollRef = useRef();
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 font-mono text-xs h-48 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
        <div className="flex items-center gap-2">
            <TerminalIcon size={14} className="text-zinc-500" />
            <span className="font-semibold text-zinc-400">System Logs</span>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-1.5 scrollbar-hide text-[11px]">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-3 text-zinc-400 hover:text-zinc-300 transition-colors">
            <span className="text-zinc-600">[{log.time}]</span>
            <span className={log.type === 'error' ? 'text-red-400' : log.type === 'warn' ? 'text-amber-400' : 'text-zinc-300'}>
                {log.msg}
            </span>
          </div>
        ))}
        {logs.length === 0 && <div className="text-zinc-600">Awaiting telemetry...</div>}
      </div>
    </div>
  );
};

const ScreenshotLightbox = ({ leakId, onClose }) => {
  const { fetchScreenshot } = useNasoStore();
  const [imgUrl, setImgUrl] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (leakId) {
      setLoading(true);
      fetchScreenshot(leakId).then(url => {
        setImgUrl(url);
        setLoading(false);
      });
    } else {
      setImgUrl(null);
    }
    return () => { if (imgUrl) URL.revokeObjectURL(imgUrl); };
  }, [leakId]);

  return (
    <Dialog open={!!leakId} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl bg-black/95 border-naso-accent/20 p-0 overflow-hidden backdrop-blur-3xl shadow-[0_0_150px_rgba(59,130,246,0.15)] rounded-none">
        <div className="relative aspect-video w-full bg-[#050507] flex items-center justify-center border-4 border-white/5">
          {loading ? (
            <div className="flex flex-col items-center gap-6">
              <Radar className="animate-spin text-naso-accent" size={64} />
              <p className="text-[10px] font-black uppercase tracking-[0.5em] text-naso-accent animate-pulse">Reconstructing Forensic Artifact...</p>
            </div>
          ) : imgUrl ? (
            <div className="relative w-full h-full p-10">
                <img 
                    src={imgUrl} 
                    alt="Forensic Evidence"
                    className="w-full h-full object-contain shadow-[0_0_50px_rgba(0,0,0,1)]"
                />
                <div className="absolute inset-0 pointer-events-none border-[20px] border-black/20"></div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 text-red-500/50">
                <ShieldAlert size={48} />
                <p className="text-xs font-black uppercase tracking-widest">Access Denied • Artifact Corrupted</p>
            </div>
          )}
          <div className="absolute top-0 left-0 w-full p-8 bg-gradient-to-b from-black/90 via-black/40 to-transparent flex justify-between items-start z-10">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-naso-accent shadow-[0_0_20px_rgba(59,130,246,0.4)]"><ImageIcon size={20} className="text-white" /></div>
              <div className="flex flex-col gap-1">
                <p className="text-[10px] font-black uppercase tracking-[0.4em] text-naso-accent">Forensic Evidence Chain</p>
                <p className="text-lg font-black text-white tracking-tighter uppercase">Artifact-ID: {leakId?.toUpperCase()}</p>
              </div>
            </div>
            <div className="flex gap-2">
                <Button variant="outline" className="border-white/10 text-white hover:bg-white/5 text-[10px] font-black uppercase tracking-widest h-10 px-6">Download RAW</Button>
                <Button variant="ghost" size="icon" onClick={onClose} className="text-white hover:bg-red-500/20 hover:text-red-500 h-10 w-10 transition-all"><X size={24} /></Button>
            </div>
          </div>
          
          {/* Metadata Sidebar in Lightbox */}
          <div className="absolute bottom-8 right-8 w-64 naso-glass p-6 space-y-4 border-naso-accent/20">
             <div className="space-y-1">
                <p className="text-[8px] font-black text-naso-accent uppercase tracking-widest">Metadata Hash</p>
                <p className="text-[9px] font-mono text-white truncate">SHA256: 8f2c3a9d...f4e1</p>
             </div>
             <div className="space-y-1">
                <p className="text-[8px] font-black text-naso-accent uppercase tracking-widest">Timestamp</p>
                <p className="text-[9px] font-mono text-white uppercase">{new Date().toISOString()}</p>
             </div>
             <Badge className="w-full justify-center bg-emerald-500/10 text-emerald-500 border-emerald-500/20 font-black">UNMODIFIED EVIDENCE</Badge>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const NotificationItem = ({ alert }) => (
  <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all cursor-pointer relative overflow-hidden">
    <div className="flex gap-4">
      <div className={`p-2 rounded-lg ${alert.severity_score >= 80 ? 'bg-red-500/10 text-red-500' : 'bg-blue-500/10 text-blue-500'}`}>
        {alert.severity_score >= 80 ? <AlertOctagon size={16} /> : <Zap size={16} />}
      </div>
      <div className="flex-1 space-y-1">
        <div className="flex justify-between items-start">
          <p className={`text-xs font-semibold ${alert.severity_score >= 80 ? 'text-red-400' : 'text-blue-400'}`}>
            {alert.severity_score >= 80 ? 'Critical Breach' : 'Intelligence Match'}
          </p>
          <span className="text-[10px] text-zinc-500">{new Date(alert.discovered_at).toLocaleTimeString()}</span>
        </div>
        <p className="text-xs text-zinc-400">
          Artifact identified from <span className="text-zinc-200 font-medium">{alert.source}</span>.
        </p>
      </div>
    </div>
  </div>
);

const StatCard = ({ title, value, icon: Icon, description, trend, trendValue, color = 'blue-500' }) => (
  <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] shadow-sm relative overflow-hidden rounded-2xl transition-all duration-300 hover:bg-[#1C1C1E]/80">
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-[13px] font-medium text-zinc-400">
        {title}
      </CardTitle>
      <div className="p-1.5 rounded-full bg-white/[0.04]">
        <Icon className={`h-4 w-4 text-zinc-300`} strokeWidth={1.5} />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-baseline gap-2">
        <div className="text-3xl font-semibold tracking-tight text-white mb-1">{value}</div>
        {trend && (
          <span className={`flex items-center text-[12px] font-medium px-1.5 py-0.5 rounded-md ${trend === 'up' ? 'text-[#FF453A] bg-[#FF453A]/10' : 'text-[#32D74B] bg-[#32D74B]/10'}`}>
            {trend === 'up' ? <TrendingUp size={12} className="mr-1" strokeWidth={2.5}/> : <TrendingDown size={12} className="mr-1" strokeWidth={2.5}/>} 
            {trendValue}%
          </span>
        )}
      </div>
      <p className="text-[11px] text-zinc-500">
        {description}
      </p>
    </CardContent>
  </Card>
);

const LeakRow = ({ leak, onInspect }) => (
  <TableRow className="border-b border-white/[0.05] hover:bg-white/[0.03] transition-colors">
    <TableCell className="font-mono text-[11px] text-zinc-400">
      {leak.id.slice(0,12).toUpperCase()}
    </TableCell>
    <TableCell>
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08]">
          {leak.source.toLowerCase().includes('github') && <Code2 size={13} className="text-zinc-300" strokeWidth={1.5} />}
          {leak.source.toLowerCase().includes('telegram') && <MessageSquare size={13} className="text-[#0A84FF]" strokeWidth={1.5} />}
          {leak.source.toLowerCase().includes('darkweb') && <Shield size={13} className="text-purple-400" strokeWidth={1.5} />}
          {!['github', 'telegram', 'darkweb'].some(s => leak.source.toLowerCase().includes(s)) && <Globe size={13} className="text-zinc-300" strokeWidth={1.5} />}
        </div>
        <div className="flex flex-col">
          <span className="text-[13px] font-medium text-white tracking-tight">{leak.source.split(':')[0]}</span>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <Badge variant="outline" className={`text-[10px] font-medium border-white/10 ${leak.severity_score >= 80 ? 'text-[#FF453A] bg-[#FF453A]/10' : leak.severity_score >= 50 ? 'text-orange-400 bg-orange-400/10' : 'text-[#32D74B] bg-[#32D74B]/10'}`}>
        Score: {leak.severity_score}
      </Badge>
    </TableCell>
    <TableCell className="max-w-[200px] truncate text-[12px] text-zinc-400">
      {leak.content_snippet ? leak.content_snippet : 'Encrypted Blob'}
    </TableCell>
    <TableCell className="text-right">
      <div className="flex items-center justify-end gap-2">
        {leak.screenshot_path && (
          <Button onClick={() => onInspect(leak.id, true)} variant="ghost" size="sm" className="h-8 w-8 p-0 text-zinc-400 hover:text-white hover:bg-white/10 rounded-full">
            <ImageIcon size={14} strokeWidth={1.5} />
          </Button>
        )}
        <Button onClick={() => onInspect(leak.id)} variant="outline" size="sm" className="h-7 text-[11px] font-medium border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 bg-transparent rounded-full px-3">
          Inspect
        </Button>
      </div>
    </TableCell>
  </TableRow>
);

export default function App() {
  const { 
    leaks, fetchLeaks, identities, fetchIdentities, 
    auditLogs, fetchAuditLogs,
    darkWebResults, searchDarkWeb,
    exportMassiveDossier,
    selectedIdentityInsights, fetchIdentityInsights, clearSelectedIdentity,
    toggleIdentityProtection,
    isLoading, systemStatus, fetchSystemStatus, error, clearError,
    addIdentity, updateProfile
  } = useNasoStore();

  const [activeView, setActiveView] = useState('dashboard');
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [viewingScreenshotId, setViewingScreenshotId] = useState(null);
  const [reconQuery, setReconQuery] = useState('');
  const [terminalLogs, setTerminalLogs] = useState([]);

  // UI state for modals
  const [isAddIdentityOpen, setIsAddIdentityOpen] = useState(false);
  const [newIdentityIdentifier, setNewIdentityIdentifier] = useState('');
  const [newIdentityType, setNewIdentityType] = useState('person');

  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [editProfileEmailState, setEditProfileEmailState] = useState('f.salmi@naso-engine.io');

  // Mock terminal logs effect
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

  useEffect(() => {
    fetchLeaks();
    fetchSystemStatus();
    fetchIdentities();
    if (activeView === 'audit') fetchAuditLogs();
    
    const interval = setInterval(() => {
      fetchLeaks();
      fetchSystemStatus();
      if (activeView === 'identities') fetchIdentities();
      if (activeView === 'audit') fetchAuditLogs();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchLeaks, fetchSystemStatus, fetchIdentities, fetchAuditLogs, activeView]);

  const severityData = useMemo(() => [
    { name: 'Critical', value: leaks.filter(l => l.severity_score >= 80).length, color: '#ef4444' },
    { name: 'High', value: leaks.filter(l => l.severity_score >= 50 && l.severity_score < 80).length, color: '#f97316' },
    { name: 'Medium', value: leaks.filter(l => l.severity_score < 50).length, color: '#3b82f6' },
  ].filter(d => d.value > 0), [leaks]);

  const timelineData = useMemo(() => leaks
    .sort((a, b) => new Date(a.discovered_at) - new Date(b.discovered_at))
    .reduce((acc, l) => {
      const date = new Date(l.discovered_at).toLocaleDateString();
      const existing = acc.find(d => d.date === date);
      if (existing) { existing.count += 1; } else { acc.push({ date, count: 1 }); }
      return acc;
    }, []), [leaks]);

  return (
    <div className="flex h-screen bg-[#020203] text-zinc-100 overflow-hidden font-sans selection:bg-naso-accent/30 selection:text-white relative">
      <TacticalOverlay />
      
      <aside className="w-[260px] bg-[#1C1C1E]/60 backdrop-blur-3xl border-r border-white/[0.08] flex flex-col z-20">
        <div className="p-6 flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <div className="bg-[#0A84FF] p-2 rounded-xl shadow-sm">
              <Radar size={18} className="text-white" strokeWidth={2} />
            </div>
            <div className="flex flex-col">
              <span className="text-[15px] font-semibold tracking-tight text-white">NASO Engine</span>
              <span className="text-[11px] text-zinc-400 font-medium">Forensic OS v0.1</span>
            </div>
          </div>
          
          <div className="bg-white/[0.03] p-3 rounded-xl border border-white/[0.05] space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-medium text-zinc-400">Class</span>
                <Badge variant="outline" className="text-[10px] h-5 border-white/[0.1] bg-white/[0.02]">Root / Lvl 5</Badge>
            </div>
            <div className="flex justify-between items-center">
                <span className="text-[11px] font-medium text-zinc-400">Vault</span>
                <span className="text-[11px] text-[#32D74B] font-medium flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#32D74B]"></div> Active</span>
            </div>
          </div>
        </div>
        
        <nav className="flex-1 px-3 space-y-0.5">
          <p className="px-3 py-2 text-[11px] font-medium text-zinc-500 mb-1">Navigation</p>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('dashboard')}
            className={`w-full justify-start gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium ${activeView === 'dashboard' ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`}
          >
            <LayoutDashboard size={16} strokeWidth={activeView === 'dashboard' ? 2 : 1.5} /> <span>Dashboard</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('topology')}
            className={`w-full justify-start gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium ${activeView === 'topology' ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`}
          >
            <Share2 size={16} strokeWidth={activeView === 'topology' ? 2 : 1.5} /> <span>Neural Topology</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('identities')}
            className={`w-full justify-start gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium ${activeView === 'identities' ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`}
          >
            <Fingerprint size={16} strokeWidth={activeView === 'identities' ? 2 : 1.5} /> <span>Master Identities</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('dark-search')}
            className={`w-full justify-start gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium ${activeView === 'dark-search' ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`}
          >
            <Flame size={16} strokeWidth={activeView === 'dark-search' ? 2 : 1.5} /> <span>Dark Recon Probe</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('audit')}
            className={`w-full justify-start gap-3 h-9 px-3 rounded-lg transition-all text-[13px] font-medium ${activeView === 'audit' ? 'bg-[#0A84FF] text-white shadow-sm' : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'}`}
          >
            <ScrollText size={16} strokeWidth={activeView === 'audit' ? 2 : 1.5} /> <span>Audit Logs</span>
          </Button>
        </nav>

        <div className="p-4 mt-auto border-t border-white/[0.08] bg-transparent">
          <TerminalLog logs={terminalLogs} />
          <div className="flex items-center gap-3 mt-4 p-2 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.06] transition-all cursor-pointer">
            <div className="w-8 h-8 rounded-lg bg-[#0A84FF] shadow-sm flex items-center justify-center">
              <span className="text-white font-bold text-xs">FS</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[13px] font-medium text-white tracking-tight">Fabrizio Salmi</span>
              <span className="text-[10px] text-zinc-400">System Architect</span>
            </div>
            <Button variant="ghost" size="icon" onClick={() => setIsEditProfileOpen(true)} className="ml-auto h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10"><Settings size={14} /></Button>
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative overflow-hidden bg-black">
        <header className="h-16 border-b border-white/[0.08] bg-[#1C1C1E]/50 backdrop-blur-xl flex items-center justify-between px-6 z-30">
          <div className="flex items-center gap-8">
            <div className="flex flex-col">
              <h2 className="text-[14px] font-semibold text-white tracking-tight flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-blue-500 flex items-center justify-center shadow-md">
                    <Crosshair size={12} className="text-white" strokeWidth={2.5} />
                </div>
                {activeView.charAt(0).toUpperCase() + activeView.slice(1).replace('-', ' ')}
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
              onClick={() => setIsNotificationsOpen(true)}
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

        <div className="flex-1 overflow-y-auto p-8 relative scrollbar-hide">
          <div className="max-w-[1600px] mx-auto space-y-8">
            {activeView === 'dashboard' ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <StatCard title="Intelligence Stream" value={leaks.length} icon={AlertTriangle} description="Detected Artifacts"  trend="up" trendValue="24" />
                  <StatCard title="Critical Breaches" value={leaks.filter(l => l.severity_score >= 80).length} icon={Target} description="High-Impact Recon" trend="up" trendValue="18"  />
                  <StatCard title="Active Targets" value={identities.length} icon={Users} description="Monitored Assets" trend="down" trendValue="4" />
                  <StatCard title="Infrastructure Load" value="18.4%" icon={Cpu} description="Worker Cluster Utilization" trend="down" trendValue="2" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <Card className="bg-zinc-950 border-zinc-800 overflow-hidden">
                    <CardHeader className="pb-4 border-b border-zinc-800/50 bg-zinc-900/10">
                      <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                        <PieChartIcon size={16} className="text-zinc-500" /> Intelligence Distribution
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="h-80 pt-8">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={severityData} innerRadius={85} outerRadius={110} paddingAngle={10} dataKey="value" stroke="none">
                            {severityData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                          </Pie>
                          <Tooltip 
                            contentStyle={{ 
                                backgroundColor: 'rgba(5, 5, 7, 0.98)', 
                                backdropFilter: 'blur(20px)', 
                                border: '1px solid rgba(59,130,246,0.3)', 
                                borderRadius: '16px', 
                                fontSize: '10px',
                                color: '#fff',
                                textTransform: 'uppercase',
                                fontWeight: '900',
                                letterSpacing: '0.1em'
                            }} 
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  <Card className="lg:col-span-2 bg-zinc-950 border-zinc-800 overflow-hidden">
                    <CardHeader className="border-b border-zinc-800/50 bg-zinc-900/10 py-4">
                      <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                        <Activity size={16} className="text-emerald-500" /> Forensic Timeline Telemetry
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="h-80 pt-10">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timelineData}>
                          <defs>
                            <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                          <XAxis dataKey="date" stroke="#71717a" fontSize={12} axisLine={false} tickLine={false} tickMargin={10} />
                          <YAxis stroke="#71717a" fontSize={12} axisLine={false} tickLine={false} />
                          <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorCount)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden shadow-sm relative rounded-2xl">
                  <CardHeader className="flex flex-row items-center justify-between p-6 border-b border-white/[0.05]">
                    <div className="flex items-center gap-4">
                      <div className="p-2.5 rounded-xl bg-white/[0.05] border border-white/[0.08]">
                        <Database size={18} className="text-[#0A84FF]" strokeWidth={1.5} />
                      </div>
                      <div className="flex flex-col">
                        <CardTitle className="text-[17px] tracking-tight font-semibold text-white">Live Intelligence Stream</CardTitle>
                        <p className="text-[13px] text-zinc-500">Real-time Artifact Ingestion & Analysis</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button onClick={() => exportMassiveDossier()} variant="outline" className="border-white/10 text-zinc-300 hover:bg-white/10 hover:text-white text-[12px] h-8 px-4 rounded-full transition-all bg-transparent">
                            <Download size={14} className="mr-2" strokeWidth={1.5} /> Export Dossier
                        </Button>
                        <Button onClick={() => fetchLeaks()} variant="secondary" className="h-8 px-4 text-[12px] bg-white text-black hover:bg-zinc-200 rounded-full font-medium">
                        {isLoading ? <Loader2 size={14} className="animate-spin mr-2" /> : <History size={14} className="mr-2" strokeWidth={1.5} />}
                        Sync Intelligence
                        </Button>
                    </div>
                  </CardHeader>
                  <Table>
                    <TableHeader className="bg-black/20">
                      <TableRow className="border-b border-white/[0.05] h-11">
                        <TableHead className="text-[12px] font-medium text-zinc-500">Artifact Signature</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Vector Origin</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Threat Risk</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Forensic Metadata</TableHead>
                        <TableHead className="text-right text-[12px] font-medium text-zinc-500">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {leaks.map((leak) => (
                        <LeakRow 
                          key={leak.id} 
                          leak={leak} 
                          onInspect={(id, isScreenshot) => {
                            if (isScreenshot) {
                              setViewingScreenshotId(id);
                            } else {
                              setActiveView('identities');
                            }
                          }} 
                        />
                      ))}
                      {leaks.length === 0 && (
                          <TableRow>
                              <TableCell colSpan={5} className="h-40 text-center text-zinc-600 font-mono italic text-xs uppercase tracking-[0.3em]">
                                 --- Scrutinizing Data Streams... No Artifacts Detected ---
                              </TableCell>
                          </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </Card>
                <ScreenshotLightbox leakId={viewingScreenshotId} onClose={() => setViewingScreenshotId(null)} />
              </>
            ) : activeView === 'topology' ? (
              <div className="h-[calc(100vh-110px)] flex flex-col gap-5">
                <div className="flex justify-between items-center">
                  <div>
                    <h1 className="text-[22px] font-semibold tracking-tight text-white">Intelligence Topology</h1>
                    <p className="text-[13px] text-zinc-500 mt-0.5">Relationship map across cross-tenant artifacts</p>
                  </div>
                  <Button onClick={() => fetchGraphData()} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
                    <Radar size={15} className="mr-2" strokeWidth={2} /> Re-Scan
                  </Button>
                </div>
                <div className="flex-1 rounded-2xl border border-white/[0.08] bg-[#1C1C1E]/40 overflow-hidden">
                    <NetworkGraphPro data={graphData} />
                </div>
              </div>
            ) : activeView === 'identities' ? (
              <div className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h1 className="text-[22px] font-semibold tracking-tight text-white">Master Identities</h1>
                    <p className="text-[13px] text-zinc-500 mt-0.5">Deep forensic reconnaissance & target profiling</p>
                  </div>
                  <Button onClick={() => setIsAddIdentityOpen(true)} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
                    <UserPlus size={15} className="mr-2" strokeWidth={2} /> Add Identity
                  </Button>
                </div>

                <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden rounded-2xl shadow-sm">
                  <Table>
                    <TableHeader className="bg-black/20">
                      <TableRow className="border-b border-white/[0.05] h-11">
                        <TableHead className="text-[12px] font-medium text-zinc-500 pl-5">Asset Identifier</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Type</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Threat Exposure</TableHead>
                        <TableHead className="text-right pr-5 text-[12px] font-medium text-zinc-500">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {identities.map((id) => (
                        <IdentityRow key={id.id} identity={id} onDetails={() => fetchIdentityInsights(id.id)} />
                      ))}
                      {identities.length === 0 && (
                          <TableRow>
                              <TableCell colSpan={4} className="h-40 text-center text-zinc-600 text-[13px]">
                                 No identities registered yet.
                              </TableCell>
                          </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </Card>
              </div>
            ) : activeView === 'dark-search' ? (
              <div className="space-y-8">
                <div>
                  <h1 className="text-[22px] font-semibold tracking-tight text-white">Dark Recon Probe</h1>
                  <p className="text-[13px] text-zinc-500 mt-0.5">Scrutinize encrypted databases and active .onion services</p>
                </div>

                <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] rounded-2xl overflow-hidden">
                  <CardContent className="p-8">
                    <div className="flex flex-col items-center gap-8 max-w-2xl mx-auto">
                      <div className="p-5 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/20">
                          <Radar size={48} className="text-[#0A84FF]" strokeWidth={1.5} />
                      </div>
                      <div className="space-y-2 text-center">
                          <h2 className="text-[20px] font-semibold tracking-tight text-white">Onion Intelligence Probe</h2>
                          <p className="text-[13px] text-zinc-500 max-w-md mx-auto leading-relaxed">Search encrypted databases and .onion services for forensic identifiers, emails, hashes, or signatures.</p>
                      </div>
                      <div className="w-full flex gap-3 p-2 pl-4 bg-black/40 rounded-full border border-white/[0.08] focus-within:border-[#0A84FF]/50 transition-all">
                          <input 
                              type="text" 
                              placeholder="Signature, email, or hash..."
                              value={reconQuery}
                              onChange={(e) => setReconQuery(e.target.value)}
                              onKeyDown={(e) => e.key === 'Enter' && searchDarkWeb(reconQuery)}
                              className="flex-1 bg-transparent text-[14px] text-white placeholder:text-zinc-600 outline-none"
                          />
                          <Button onClick={() => searchDarkWeb(reconQuery)} className="bg-[#0A84FF] hover:bg-[#007AFF] text-white font-medium text-[13px] px-6 rounded-full h-10 shadow-sm">
                              {isLoading ? <Loader2 size={15} className="animate-spin" /> : 'Launch Probe'}
                          </Button>
                      </div>
                      <div className="flex gap-6 text-[11px] font-medium text-zinc-500">
                          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#32D74B]"></div> Ahmia Active</span>
                          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]"></div> Tor Circuit On</span>
                          <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]"></div> Correlation On</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {darkWebResults.length > 0 && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                            <h3 className="text-[14px] font-semibold text-white flex items-center gap-2">
                                <ShieldAlert size={16} className="text-[#FF453A]" strokeWidth={1.5} /> Intercepted Intel ({darkWebResults.length})
                            </h3>
                            <Button variant="ghost" className="text-[12px] font-medium text-zinc-500 hover:text-white h-8 rounded-full px-3">Clear Results</Button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {darkWebResults.map((res, i) => (
                                <Card key={i} className="bg-[#1C1C1E]/50 border-white/[0.08] p-5 hover:border-white/[0.15] transition-all rounded-2xl">
                                    <div className="flex justify-between items-start mb-4">
                                        <Badge className="bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 font-medium text-[10px]">Match Found</Badge>
                                        <ExternalLink size={15} className="text-zinc-600 hover:text-white transition-colors cursor-pointer" strokeWidth={1.5} />
                                    </div>
                                    <h4 className="text-[15px] font-semibold text-white mb-2 tracking-tight">{res.title}</h4>
                                    <p className="text-[11px] font-mono text-zinc-500 break-all bg-black/30 p-3 rounded-lg border border-white/[0.05]">{res.url}</p>
                                    <div className="flex gap-2 mt-4">
                                        <Button className="flex-1 text-[12px] font-medium bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 hover:bg-[#0A84FF]/20 transition-all rounded-full h-9">Deep Scrape</Button>
                                        <Button variant="ghost" className="text-[12px] font-medium border border-white/10 rounded-full h-9 px-4 text-zinc-400 hover:text-white">Proxy Link</Button>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h1 className="text-[22px] font-semibold tracking-tight text-white">Audit & Compliance</h1>
                    <p className="text-[13px] text-zinc-500 mt-0.5">Immutable forensic accountability — every operation hashed and logged</p>
                  </div>
                  <Button onClick={() => fetchAuditLogs()} variant="outline" className="h-9 px-5 text-[13px] font-medium border-white/10 bg-transparent text-zinc-300 hover:text-white hover:bg-white/10 rounded-full">
                    <Download size={14} className="mr-2" strokeWidth={1.5} /> Export CSV
                  </Button>
                </div>

                <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden rounded-2xl shadow-sm">
                  <Table>
                    <TableHeader className="bg-black/20">
                      <TableRow className="border-b border-white/[0.05] h-11">
                        <TableHead className="text-[12px] font-medium text-zinc-500 pl-5">Operator & Action</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Asset Vector</TableHead>
                        <TableHead className="text-[12px] font-medium text-zinc-500">Details</TableHead>
                        <TableHead className="text-right pr-5 text-[12px] font-medium text-zinc-500">Timestamp (UTC)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditLogs.map((log) => (
                        <AuditLogRow key={log.id} log={log} />
                      ))}
                      {auditLogs.length === 0 && (
                          <TableRow>
                              <TableCell colSpan={4} className="h-40 text-center text-zinc-600 text-[13px]">
                                 No audit entries logged yet.
                              </TableCell>
                          </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </Card>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Side Sheets & Dialogs */}
      <Sheet open={isNotificationsOpen} onOpenChange={setIsNotificationsOpen}>
        <SheetContent className="w-[400px] sm:w-[480px] bg-[#1C1C1E]/95 backdrop-blur-3xl border-l border-white/[0.08] p-0 shadow-2xl">
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
            <SheetDescription className="text-[12px] text-zinc-500 mt-1">Critical artifacts identified in the last 24h.</SheetDescription>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-5 space-y-3 scrollbar-hide">
            {leaks.filter(l => l.severity_score >= 80).map(alert => <NotificationItem key={alert.id} alert={alert} />)}
            {leaks.filter(l => l.severity_score >= 80).length === 0 && (
                 <div className="h-48 flex flex-col items-center justify-center text-zinc-600 gap-4">
                    <ShieldCheck size={36} className="text-[#32D74B]" strokeWidth={1.5} />
                    <p className="text-[13px] font-medium text-zinc-500">No critical threats identified</p>
                 </div>
            )}
          </div>
          <div className="p-5 border-t border-white/[0.08]">
            <Button className="w-full h-10 font-medium text-[13px] bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full">Mark All as Resolved</Button>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={!!selectedIdentityInsights} onOpenChange={clearSelectedIdentity}>
        <DialogContent className="max-w-3xl bg-[#1C1C1E]/95 backdrop-blur-3xl border-white/[0.08] overflow-hidden p-0 rounded-2xl shadow-2xl">
          {selectedIdentityInsights && (
            <div className="flex flex-col max-h-[85vh]">
              {/* Header */}
              <div className="p-6 border-b border-white/[0.08] flex items-center gap-5">
                <div className={`p-4 rounded-2xl ${selectedIdentityInsights.identity.risk_score >= 80 ? 'bg-[#FF453A]/10 border border-[#FF453A]/20' : 'bg-[#0A84FF]/10 border border-[#0A84FF]/20'}`}>
                  <Users size={28} strokeWidth={1.5} className={selectedIdentityInsights.identity.risk_score >= 80 ? 'text-[#FF453A]' : 'text-[#0A84FF]'} />
                </div>
                <div className="flex-1">
                  <h2 className="text-[20px] font-semibold tracking-tight text-white">{selectedIdentityInsights.identity.identifier}</h2>
                  <div className="flex items-center gap-4 mt-1">
                    <span className="text-[12px] text-zinc-500 flex items-center gap-1.5"><Fingerprint size={12} strokeWidth={1.5} /> {selectedIdentityInsights.identity.type}</span>
                    <span className="text-zinc-700">·</span>
                    <span className="text-[12px] text-zinc-500 flex items-center gap-1.5"><Clock size={12} strokeWidth={1.5} /> {new Date(selectedIdentityInsights.last_seen).toLocaleDateString()}</span>
                  </div>
                </div>
                {selectedIdentityInsights.identity.risk_score >= 80 && (
                  <Badge className="bg-[#FF453A]/10 text-[#FF453A] border border-[#FF453A]/20 font-medium text-[11px]">Critical Risk</Badge>
                )}
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide">
                {/* Stats Row */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-black/30 border border-white/[0.06] rounded-2xl p-4">
                    <p className="text-[11px] font-medium text-zinc-500 mb-2">Risk Score</p>
                    <p className={`text-3xl font-semibold tracking-tight ${selectedIdentityInsights.identity.risk_score >= 80 ? 'text-[#FF453A]' : 'text-white'}`}>{selectedIdentityInsights.identity.risk_score}</p>
                  </div>
                  <div className="bg-black/30 border border-white/[0.06] rounded-2xl p-4">
                    <p className="text-[11px] font-medium text-zinc-500 mb-2">Leaked Vectors</p>
                    <p className="text-3xl font-semibold tracking-tight text-white">{selectedIdentityInsights.total_leaks}</p>
                  </div>
                  <div className="bg-black/30 border border-white/[0.06] rounded-2xl p-4 flex flex-col justify-between">
                    <p className="text-[11px] font-medium text-zinc-500 mb-3">Priority</p>
                    <Button onClick={() => toggleIdentityProtection(selectedIdentityInsights.identity.id, !selectedIdentityInsights.identity.is_protected)} size="sm" className={`w-full text-[12px] font-medium rounded-full h-9 ${selectedIdentityInsights.identity.is_protected ? 'bg-[#FFD60A]/10 text-[#FFD60A] border border-[#FFD60A]/20 hover:bg-[#FFD60A]/20' : 'bg-white/5 text-zinc-300 border border-white/10 hover:bg-white/10'}`}>
                      {selectedIdentityInsights.identity.is_protected ? <Lock size={14} className="mr-2" strokeWidth={2} /> : <Unlock size={14} className="mr-2" strokeWidth={2} />}
                      {selectedIdentityInsights.identity.is_protected ? 'VIP Protected' : 'Set as VIP'}
                    </Button>
                  </div>
                </div>

                {/* Merged Identities */}
                {selectedIdentityInsights.merged_identities.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-[13px] font-semibold text-zinc-300 flex items-center gap-2"><Workflow size={15} strokeWidth={1.5} /> Merged Identity Network <Badge className="ml-1 bg-white/5 text-zinc-400 border border-white/10 text-[10px]">{selectedIdentityInsights.merged_identities.length}</Badge></h4>
                    <div className="grid grid-cols-2 gap-2">
                      {selectedIdentityInsights.merged_identities.map(slave => (
                        <div key={slave.id} className="p-3 rounded-xl bg-black/30 border border-white/[0.06] flex items-center justify-between hover:border-[#0A84FF]/30 transition-all">
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 bg-white/[0.04] rounded-lg"><UserPlus size={13} strokeWidth={1.5} className="text-zinc-400" /></div>
                            <span className="text-[12px] font-medium text-zinc-200">{slave.identifier}</span>
                          </div>
                          <Badge variant="outline" className="text-[10px] border-white/10 text-zinc-500">{slave.type}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Compromise Timeline */}
                <div className="space-y-3">
                  <h4 className="text-[13px] font-semibold text-zinc-300 flex items-center gap-2"><History size={15} strokeWidth={1.5} /> Compromise Timeline</h4>
                  <div className="space-y-2">
                    {selectedIdentityInsights.leaks.map((leak) => (
                      <div key={leak.id} className="bg-black/30 border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.12] transition-all">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-[13px] font-medium text-zinc-200 flex items-center gap-2"><Globe size={13} strokeWidth={1.5} className="text-zinc-500" />{leak.source}</span>
                          <Badge className={`text-[10px] font-medium ${leak.severity_score >= 80 ? 'bg-[#FF453A]/10 text-[#FF453A] border border-[#FF453A]/20' : 'bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20'}`}>{leak.severity_score}%</Badge>
                        </div>
                        <p className="text-[11px] font-mono text-zinc-500 bg-black/30 p-2.5 rounded-lg border border-white/[0.05]">
                            {leak.content_snippet ? `"${leak.content_snippet}"` : '<encrypted_payload>'}
                        </p>
                        <p className="text-[10px] text-zinc-600 mt-2">{new Date(leak.discovered_at).toLocaleString()}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* Footer */}
              <div className="p-5 border-t border-white/[0.08] flex justify-end gap-3">
                <Button variant="outline" className="border-white/10 h-9 px-5 text-[13px] font-medium rounded-full hover:bg-white/5 text-zinc-300" onClick={clearSelectedIdentity}>Close</Button>
                <Button className="bg-[#0A84FF] hover:bg-[#007AFF] text-white h-9 px-5 text-[13px] font-medium rounded-full shadow-sm">
                    <Download size={14} className="mr-2" strokeWidth={1.5} /> Export Evidence
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Add Identity Dialog ── */}
      <Dialog open={isAddIdentityOpen} onOpenChange={setIsAddIdentityOpen}>
        <DialogContent className="max-w-md bg-[#1C1C1E]/95 backdrop-blur-3xl border-white/[0.08] rounded-2xl shadow-2xl p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-5 border-b border-white/[0.08]">
            <DialogTitle className="text-[17px] font-semibold text-white tracking-tight">Register Monitored Identity</DialogTitle>
            <DialogDescription className="text-[13px] text-zinc-500">Track a new asset across intelligence streams</DialogDescription>
          </DialogHeader>
          <div className="p-6 space-y-5">
            <div>
              <label className="text-[12px] font-medium text-zinc-400 block mb-2">Identifier / Keyword</label>
              <input 
                type="text" 
                value={newIdentityIdentifier}
                onChange={e => setNewIdentityIdentifier(e.target.value)}
                placeholder="e.g. j.doe@corp.com or handle123"
                className="w-full bg-black/40 border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white placeholder:text-zinc-600 focus:border-[#0A84FF]/50 focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="text-[12px] font-medium text-zinc-400 block mb-2">Asset Type</label>
              <select 
                value={newIdentityType}
                onChange={e => setNewIdentityType(e.target.value)}
                className="w-full bg-black/40 border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white focus:border-[#0A84FF]/50 focus:outline-none transition-colors appearance-none"
              >
                <option value="person">Person (Email / Name)</option>
                <option value="organization">Organization (Domain)</option>
                <option value="crypto">Cryptocurrency Wallet</option>
                <option value="credential">Infrastructure Credential</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 px-6 pb-6">
            <Button variant="ghost" onClick={() => setIsAddIdentityOpen(false)} className="h-9 px-5 text-[13px] rounded-full border border-white/10 text-zinc-400 hover:text-white hover:bg-white/5">Cancel</Button>
            <Button 
              className="h-9 px-6 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm"
              disabled={isLoading || !newIdentityIdentifier}
              onClick={() => {
                addIdentity(newIdentityIdentifier, newIdentityType);
                setIsAddIdentityOpen(false);
                setNewIdentityIdentifier('');
              }}
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : 'Register Identity'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Edit Profile Dialog ── */}
      <Dialog open={isEditProfileOpen} onOpenChange={setIsEditProfileOpen}>
        <DialogContent className="max-w-md bg-[#1C1C1E]/95 backdrop-blur-3xl border-white/[0.08] rounded-2xl shadow-2xl p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-5 border-b border-white/[0.08]">
            <DialogTitle className="text-[17px] font-semibold text-white tracking-tight">Edit Operator Profile</DialogTitle>
          </DialogHeader>
          <div className="p-6 space-y-5">
            <div>
              <label className="text-[12px] font-medium text-zinc-400 block mb-2">Email Address</label>
              <input 
                type="email" 
                value={editProfileEmailState}
                onChange={e => setEditProfileEmailState(e.target.value)}
                className="w-full bg-black/40 border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white focus:border-[#0A84FF]/50 focus:outline-none transition-colors"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 px-6 pb-6">
            <Button variant="ghost" onClick={() => setIsEditProfileOpen(false)} className="h-9 px-5 text-[13px] rounded-full border border-white/10 text-zinc-400 hover:text-white hover:bg-white/5">Cancel</Button>
            <Button 
              className="h-9 px-6 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm"
              disabled={isLoading}
              onClick={() => {
                updateProfile(editProfileEmailState);
                setIsEditProfileOpen(false);
              }}
            >
              {isLoading ? <Loader2 size={14} className="animate-spin" /> : 'Save Changes'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Error Toast ── */}
      {error && (
        <div className="fixed bottom-6 right-6 p-4 pr-10 rounded-lg bg-red-950/80 border border-red-500/20 shadow-lg flex items-center gap-3 animate-fade-in z-50">
          <ShieldAlert className="text-red-400 shrink-0" size={16} />
          <span className="text-[12px] font-medium text-red-200">{error}</span>
          <button 
            onClick={clearError}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-red-400/70 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
          >
            <X size={13} />
          </button>
        </div>
      )}

    </div>
  );
}
