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
  Chrome
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

const TacticalOverlay = () => (
  <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
    <div className="absolute top-0 left-0 w-full h-1 bg-naso-accent/20"></div>
    <div className="absolute bottom-0 left-0 w-full h-1 bg-naso-accent/20"></div>
    <div className="absolute top-0 left-0 w-1 h-full bg-naso-accent/20"></div>
    <div className="absolute top-0 right-0 w-1 h-full bg-naso-accent/20"></div>
    
    {/* Corner Brackets */}
    <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-naso-accent/40"></div>
    <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-naso-accent/40"></div>
    <div className="absolute bottom-4 left-4 w-8 h-8 border-b-2 border-l-2 border-naso-accent/40"></div>
    <div className="absolute bottom-4 right-4 w-8 h-8 border-b-2 border-r-2 border-naso-accent/40"></div>
    
    <div className="scanline"></div>
    
    {/* Tactical Readouts */}
    <div className="absolute top-24 left-8 space-y-4 opacity-40">
        <div className="flex flex-col gap-1">
            <span className="text-[8px] font-black tracking-[0.3em] text-naso-accent uppercase">Grid Status</span>
            <span className="text-[10px] font-mono text-white">SECURED_NODE_ALFA_7</span>
        </div>
        <div className="flex flex-col gap-1">
            <span className="text-[8px] font-black tracking-[0.3em] text-naso-accent uppercase">Encryption</span>
            <span className="text-[10px] font-mono text-white">AES-256-GCM / PBKDF2</span>
        </div>
    </div>
  </div>
);

const TerminalLog = ({ logs }) => {
  const scrollRef = useRef();
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  return (
    <div className="bg-black/60 border border-white/5 rounded-xl p-4 font-mono text-[10px] h-48 flex flex-col overflow-hidden naso-glass">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/5">
        <div className="flex items-center gap-2">
            <TerminalIcon size={12} className="text-naso-accent" />
            <span className="font-black uppercase tracking-widest text-zinc-500">Live Operations Feed</span>
        </div>
        <div className="flex gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500/50"></div>
            <div className="w-1.5 h-1.5 rounded-full bg-yellow-500/50"></div>
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/50"></div>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-1 scrollbar-hide">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-3 opacity-80 hover:opacity-100 transition-opacity">
            <span className="text-naso-accent font-bold">[{log.time}]</span>
            <span className={log.type === 'error' ? 'text-red-400' : log.type === 'warn' ? 'text-yellow-400' : 'text-emerald-400'}>
                {log.msg}
            </span>
          </div>
        ))}
        {logs.length === 0 && <div className="text-zinc-700 italic">Awaiting telemetry...</div>}
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
  <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-naso-accent/30 transition-all group cursor-pointer relative overflow-hidden naso-glass">
    <div className={`absolute left-0 top-0 w-1.5 h-full ${alert.severity_score >= 80 ? 'bg-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]' : 'bg-naso-accent'}`}></div>
    <div className="flex gap-4">
      <div className={`p-3 rounded-xl ${alert.severity_score >= 80 ? 'bg-red-500/10 text-red-500' : 'bg-naso-accent/10 text-naso-accent'}`}>
        {alert.severity_score >= 80 ? <AlertOctagon size={20} /> : <Zap size={20} />}
      </div>
      <div className="flex-1 space-y-2">
        <div className="flex justify-between items-start">
          <p className={`text-[10px] font-black uppercase tracking-[0.2em] ${alert.severity_score >= 80 ? 'text-red-500' : 'text-naso-accent'}`}>
            {alert.severity_score >= 80 ? 'Critical Breach' : 'Intelligence Match'}
          </p>
          <span className="text-[9px] font-mono text-zinc-500">{new Date(alert.discovered_at).toLocaleTimeString()}</span>
        </div>
        <p className="text-xs text-zinc-300 font-medium leading-relaxed">
          Artifact identified from <span className="text-white font-black italic">{alert.source}</span>. AI Confidence: 99.4%.
        </p>
      </div>
    </div>
  </div>
);

const StatCard = ({ title, value, icon: Icon, description, trend, trendValue, color = 'naso-accent' }) => (
  <Card className="relative group overflow-hidden bg-card/40 backdrop-blur-2xl border-white/5 transition-all duration-500 hover:border-naso-accent/40 shadow-2xl naso-glass">
    <div className={`absolute -right-4 -bottom-4 p-8 opacity-[0.02] group-hover:opacity-[0.06] transition-opacity duration-700 pointer-events-none text-${color}`}>
      <Icon size={120} strokeWidth={1} />
    </div>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-[9px] font-black uppercase tracking-[0.3em] text-zinc-500 flex items-center gap-2">
        <div className={`w-1.5 h-1.5 bg-${color} rounded-full animate-pulse`}></div>
        {title}
      </CardTitle>
      <div className={`p-2.5 rounded-xl bg-white/5 group-hover:bg-${color}/10 transition-all duration-500`}>
        <Icon className={`h-4 w-4 text-${color}`} />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-baseline gap-3">
        <div className="text-5xl font-black tracking-tighter drop-shadow-2xl text-white">{value}</div>
        {trend && (
          <Badge variant="outline" className={`text-[10px] font-black py-0 px-2 ${trend === 'up' ? 'text-red-500 border-red-500/20 bg-red-500/5' : 'text-emerald-500 border-emerald-500/20 bg-emerald-500/5'}`}>
            {trend === 'up' ? '▲' : '▼'} {trendValue}%
          </Badge>
        )}
      </div>
      <p className="text-[9px] text-zinc-500 mt-4 font-black uppercase tracking-[0.2em] opacity-80">
        {description}
      </p>
    </CardContent>
  </Card>
);

const LeakRow = ({ leak, onInspect }) => (
  <TableRow className="group border-white/[0.02] hover:bg-white/[0.03] transition-colors h-20">
    <TableCell className="pl-8">
      <div className="flex items-center gap-3">
        <div className="w-1.5 h-1.5 rounded-full bg-naso-accent animate-pulse"></div>
        <div className="font-mono text-[10px] bg-white/5 text-zinc-400 px-3 py-1.5 rounded-lg border border-white/5 group-hover:border-naso-accent/30 group-hover:text-white transition-all">
          {leak.id.slice(0,12).toUpperCase()}
        </div>
      </div>
    </TableCell>
    <TableCell>
      <div className="flex items-center gap-4">
        <div className="p-2.5 rounded-xl bg-zinc-900 border border-white/5 shadow-inner">
          {leak.source.toLowerCase().includes('github') && <Github size={18} className="text-zinc-400" />}
          {leak.source.toLowerCase().includes('telegram') && <MessageSquare size={18} className="text-blue-400" />}
          {leak.source.toLowerCase().includes('darkweb') && <Shield size={18} className="text-purple-400" />}
          {!['github', 'telegram', 'darkweb'].some(s => leak.source.toLowerCase().includes(s)) && <Globe size={18} className="text-naso-accent" />}
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-black text-white uppercase tracking-tight">{leak.source.split(':')[0]}</span>
          <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-widest">{leak.source.split(':')[1] || 'Primary Stream'}</span>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center w-32">
          <span className="text-[8px] font-black text-zinc-500 tracking-tighter uppercase">Threat Probability</span>
          <span className={`text-[10px] font-mono font-black ${leak.severity_score >= 80 ? 'text-red-500' : 'text-naso-accent'}`}>{leak.severity_score}%</span>
        </div>
        <div className="w-32 h-1.5 bg-white/5 rounded-full overflow-hidden p-[1px]">
          <div 
            className={`h-full rounded-full transition-all duration-1000 ${leak.severity_score >= 80 ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]' : leak.severity_score >= 50 ? 'bg-orange-500' : 'bg-naso-accent'}`}
            style={{ width: `${leak.severity_score}%` }}
          ></div>
        </div>
      </div>
    </TableCell>
    <TableCell className="max-w-[300px] truncate text-[11px] text-zinc-400 font-mono italic">
      {leak.content_snippet ? `"${leak.content_snippet}"` : '<encrypted_forensic_blob>'}
    </TableCell>
    <TableCell className="text-right pr-8">
      <div className="flex items-center justify-end gap-3 opacity-0 group-hover:opacity-100 transition-all translate-x-4 group-hover:translate-x-0">
        {leak.screenshot_path && (
          <Button onClick={() => onInspect(leak.id, true)} variant="ghost" size="icon" className="h-10 w-10 text-naso-accent hover:bg-naso-accent/10 rounded-xl border border-transparent hover:border-naso-accent/20">
            <ImageIcon size={18} />
          </Button>
        )}
        <Button onClick={() => onInspect(leak.id)} className="h-10 px-6 text-[10px] font-black uppercase tracking-[0.2em] bg-naso-accent hover:bg-naso-accent/80 text-white shadow-lg shadow-naso-accent/30 rounded-xl">
          Initiate Recon
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
    isLoading, systemStatus, fetchSystemStatus, error 
  } = useNasoStore();

  const [activeView, setActiveView] = useState('dashboard');
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [viewingScreenshotId, setViewingScreenshotId] = useState(null);
  const [reconQuery, setReconQuery] = useState('');
  const [terminalLogs, setTerminalLogs] = useState([]);

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
      
      <aside className="w-72 bg-black/60 backdrop-blur-3xl border-r border-white/5 flex flex-col relative z-20">
        <div className="p-10 flex flex-col gap-8">
          <div className="flex items-center gap-5">
            <div className="bg-naso-accent p-3 rounded-2xl shadow-[0_0_40px_rgba(59,130,246,0.4)] border border-white/10">
              <Radar size={28} className="text-white animate-pulse" />
            </div>
            <div className="flex flex-col">
              <span className="text-3xl font-black tracking-tighter leading-none italic">NASO</span>
              <span className="text-[9px] font-black tracking-[0.5em] text-naso-accent opacity-90 uppercase mt-1.5">Forensic OS v0.1</span>
            </div>
          </div>
          
          <div className="naso-glass p-4 rounded-xl space-y-2 border-naso-accent/20">
            <div className="flex justify-between items-center">
                <span className="text-[8px] font-black uppercase text-zinc-500">Operator Class</span>
                <Badge className="bg-naso-accent/10 text-naso-accent text-[8px] font-black h-4 uppercase">Root / Level 5</Badge>
            </div>
            <div className="flex justify-between items-center">
                <span className="text-[8px] font-black uppercase text-zinc-500">Secure Vault</span>
                <span className="text-[9px] font-mono text-emerald-500 animate-pulse uppercase">Active</span>
            </div>
          </div>
        </div>
        
        <nav className="flex-1 px-6 space-y-2">
          <p className="px-4 py-4 text-[10px] font-black text-zinc-600 uppercase tracking-[0.3em]">Command Sectors</p>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('dashboard')}
            className={`w-full justify-start gap-4 h-14 px-5 rounded-2xl transition-all duration-500 ${activeView === 'dashboard' ? 'bg-naso-accent text-white shadow-naso-glow border-white/10' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
          >
            <LayoutDashboard size={20} /> <span className="text-[11px] font-black uppercase tracking-widest">Global Intelligence Feed</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('topology')}
            className={`w-full justify-start gap-4 h-14 px-5 rounded-2xl transition-all duration-500 ${activeView === 'topology' ? 'bg-naso-accent text-white shadow-naso-glow border-white/10' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
          >
            <Share2 size={20} /> <span className="text-[11px] font-black uppercase tracking-widest">Neural Topology Map</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('identities')}
            className={`w-full justify-start gap-4 h-14 px-5 rounded-2xl transition-all duration-500 ${activeView === 'identities' ? 'bg-naso-accent text-white shadow-naso-glow border-white/10' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
          >
            <Fingerprint size={20} /> <span className="text-[11px] font-black uppercase tracking-widest">Master Identity Hub</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('dark-search')}
            className={`w-full justify-start gap-4 h-14 px-5 rounded-2xl transition-all duration-500 ${activeView === 'dark-search' ? 'bg-naso-accent text-white shadow-naso-glow border-white/10' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
          >
            <Flame size={20} /> <span className="text-[11px] font-black uppercase tracking-widest">Deep Web Recon Hub</span>
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveView('audit')}
            className={`w-full justify-start gap-4 h-14 px-5 rounded-2xl transition-all duration-500 ${activeView === 'audit' ? 'bg-naso-accent text-white shadow-naso-glow border-white/10' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
          >
            <ScrollText size={20} /> <span className="text-[11px] font-black uppercase tracking-widest">Compliance Audit Log</span>
          </Button>
        </nav>

        <div className="p-8 mt-auto border-t border-white/5 bg-black/40">
          <TerminalLog logs={terminalLogs} />
          <div className="flex items-center gap-4 mt-8 p-4 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-naso-accent via-blue-700 to-black border border-white/20 shadow-xl"></div>
            <div className="flex flex-col">
              <span className="text-xs font-black text-white uppercase tracking-tight">Fabrizio Salmi</span>
              <span className="text-[9px] font-black text-naso-accent uppercase tracking-widest">System Architect</span>
            </div>
            <Button variant="ghost" size="icon" className="ml-auto h-8 w-8 rounded-full text-zinc-500 hover:text-white"><Settings size={16} /></Button>
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative overflow-hidden z-10">
        <header className="h-24 border-b border-white/5 bg-black/40 backdrop-blur-3xl flex items-center justify-between px-12 relative z-30">
          <div className="flex items-center gap-14">
            <div className="flex flex-col gap-1.5">
              <h2 className="text-sm font-black uppercase tracking-[0.4em] text-white flex items-center gap-3">
                <div className="w-2 h-2 bg-naso-accent rounded-full animate-pulse shadow-[0_0_10px_rgba(59,130,246,1)]"></div>
                Command Sector: <span className="text-naso-accent italic">{activeView.toUpperCase()}</span>
              </h2>
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em] flex items-center gap-2">
                <Crosshair size={12} className="text-zinc-700" /> System Ready • Core Operational • Telemetry Active
              </p>
            </div>
            
            <div className="hidden xl:flex items-center gap-10 px-8 py-3 bg-white/[0.03] rounded-2xl border border-white/5 naso-glass">
              <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest text-center">Engine Latency</span>
                <span className="text-xs font-black text-emerald-400 font-mono">{systemStatus?.latency_ms?.total || '0.42'}ms</span>
              </div>
              <div className="w-[1px] h-8 bg-white/5"></div>
              <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest text-center">Threat Cluster</span>
                <span className="text-xs font-black text-naso-accent font-mono uppercase">Node-Alfa-7</span>
              </div>
              <div className="w-[1px] h-8 bg-white/5"></div>
              <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest text-center">Global Pulse</span>
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></div>
                    <span className="text-xs font-black text-emerald-500 uppercase">Operational</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="relative group">
              <div className="absolute -inset-1.5 bg-naso-accent/30 blur opacity-0 group-hover:opacity-100 transition duration-700 rounded-full"></div>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setIsNotificationsOpen(true)}
                className="relative bg-white/5 hover:bg-white/10 border border-white/10 rounded-full h-12 w-12 transition-all shadow-2xl"
              >
                <Bell size={22} className="text-zinc-200" />
                <span className="absolute top-3.5 right-3.5 w-3 h-3 bg-red-500 rounded-full border-2 border-black animate-pulse"></span>
              </Button>
            </div>
            <Button className="bg-white/5 border border-white/10 hover:bg-white/10 text-white font-black text-[10px] uppercase tracking-[0.2em] h-12 px-8 rounded-2xl">Deploy Countermeasure</Button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-12 relative scrollbar-hide">
          <div className="max-w-[1600px] mx-auto space-y-12">
            {activeView === 'dashboard' ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                  <StatCard title="Intelligence Stream" value={leaks.length} icon={AlertTriangle} description="Detected Artifacts" trend="up" trendValue="24" color="naso-accent" />
                  <StatCard title="Critical Breaches" value={leaks.filter(l => l.severity_score >= 80).length} icon={Target} description="High-Impact Recon" trend="up" trendValue="18" color="red-500" />
                  <StatCard title="Active Targets" value={identities.length} icon={Users} description="Monitored Assets" trend="down" trendValue="4" color="emerald-500" />
                  <StatCard title="Infrastructure Load" value="18.4%" icon={Cpu} description="Worker Cluster Utilization" trend="down" trendValue="2" color="yellow-500" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
                  <Card className="bg-card/30 backdrop-blur-3xl border-white/5 overflow-hidden naso-glass">
                    <CardHeader className="pb-4 border-b border-white/5 bg-white/[0.02]">
                      <CardTitle className="text-[10px] font-black uppercase tracking-[0.3em] flex items-center gap-3 text-zinc-400">
                        <PieChartIcon size={16} className="text-naso-accent" /> Intelligence Distribution
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

                  <Card className="lg:col-span-2 bg-card/30 backdrop-blur-3xl border-white/5 overflow-hidden naso-glass">
                    <CardHeader className="border-b border-white/5 bg-white/[0.02] py-6">
                      <CardTitle className="text-[10px] font-black uppercase tracking-[0.3em] flex items-center gap-3 text-zinc-400">
                        <Activity size={16} className="text-emerald-500" /> Forensic Timeline Telemetry
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="h-80 pt-10">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timelineData}>
                          <defs>
                            <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="4 4" stroke="rgba(255,255,255,0.03)" vertical={false} />
                          <XAxis dataKey="date" stroke="#3f3f46" fontSize={9} axisLine={false} tickLine={false} tickMargin={20} tick={{ fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                          <YAxis stroke="#3f3f46" fontSize={9} axisLine={false} tickLine={false} tick={{ fontWeight: 900 }} />
                          <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorCount)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                <Card className="bg-card/20 backdrop-blur-3xl border-white/5 overflow-hidden shadow-[0_0_100px_rgba(0,0,0,0.5)] relative naso-glass border-t-naso-accent/20">
                  <CardHeader className="flex flex-row items-center justify-between p-10 border-b border-white/5 bg-white/[0.01]">
                    <div className="flex items-center gap-6">
                      <div className="p-4 rounded-2xl bg-naso-accent/10 border border-naso-accent/20 shadow-naso-glow">
                        <Database size={24} className="text-naso-accent" />
                      </div>
                      <div className="flex flex-col gap-1">
                        <CardTitle className="text-2xl font-black tracking-tight text-white uppercase italic">Live Intelligence Stream</CardTitle>
                        <p className="text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Real-time Artifact Ingestion & Analysis</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <Button onClick={() => exportMassiveDossier()} variant="outline" className="border-naso-accent/40 text-naso-accent hover:bg-naso-accent/10 font-black text-[10px] uppercase tracking-widest h-12 px-8 rounded-2xl transition-all">
                            <Download size={16} className="mr-3" /> Massive Forensic Dossier
                        </Button>
                        <Button onClick={() => fetchLeaks()} variant="secondary" className="h-12 px-8 text-[10px] font-black uppercase tracking-widest bg-white/5 border border-white/10 hover:bg-white/10 rounded-2xl">
                        {isLoading ? <Loader2 size={16} className="animate-spin mr-3" /> : <History size={16} className="mr-3" />}
                        Sync Intelligence
                        </Button>
                    </div>
                  </CardHeader>
                  <Table>
                    <TableHeader className="bg-white/[0.02]">
                      <TableRow className="border-white/5 h-16">
                        <TableHead className="pl-8 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Artifact Signature</TableHead>
                        <TableHead className="text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Vector Origin</TableHead>
                        <TableHead className="text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Threat Risk</TableHead>
                        <TableHead className="text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Forensic Metadata</TableHead>
                        <TableHead className="text-right pr-8 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Operational Actions</TableHead>
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
              <div className="h-[calc(100vh-250px)] space-y-8 animate-in fade-in zoom-in-95 duration-1000">
                <div className="flex justify-between items-end">
                  <div className="space-y-3">
                    <h1 className="text-6xl font-black tracking-tighter text-white italic">Intelligence Topology</h1>
                    <p className="text-zinc-500 font-black uppercase tracking-[0.2em] text-[10px]">Mapping Relationship Matrices across Cross-Tenant Artifacts</p>
                  </div>
                  <Button variant="outline" onClick={() => fetchGraphData()} className="border-naso-accent/40 text-naso-accent h-14 px-10 font-black uppercase text-[10px] tracking-widest rounded-2xl hover:bg-naso-accent/5 transition-all">
                    <Radar size={18} className="mr-3" /> Re-Scan Network Topology
                  </Button>
                </div>
                <div className="flex-1 h-full rounded-3xl border-2 border-white/5 shadow-inner bg-black/40 backdrop-blur-3xl overflow-hidden relative group">
                    <div className="absolute inset-0 bg-naso-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none"></div>
                    <NetworkGraphPro data={graphData} />
                </div>
              </div>
            ) : activeView === 'identities' ? (
              <div className="space-y-10 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                <div className="flex justify-between items-end">
                  <div className="space-y-3">
                    <h1 className="text-6xl font-black tracking-tighter text-white italic">Master Identity Hub</h1>
                    <p className="text-zinc-500 font-black uppercase tracking-[0.2em] text-[10px] max-w-2xl leading-loose">Deep Forensic Reconnaissance & Target Profiling for High-Value Monitor Assets.</p>
                  </div>
                  <Button className="bg-naso-accent hover:bg-naso-accent/80 text-white font-black text-xs h-14 px-10 rounded-2xl shadow-2xl shadow-naso-accent/40 uppercase tracking-widest">
                    <UserPlus size={18} className="mr-3" /> Register High-Value Target
                  </Button>
                </div>

                <Card className="bg-card/20 backdrop-blur-3xl border-white/5 overflow-hidden shadow-2xl naso-glass border-t-emerald-500/20">
                  <Table>
                    <TableHeader className="bg-white/[0.02]">
                      <TableRow className="border-white/5 h-16">
                        <TableHead className="pl-10 h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Asset Identifier</TableHead>
                        <TableHead className="h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Vector Type</TableHead>
                        <TableHead className="h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Threat Exposure Matrix</TableHead>
                        <TableHead className="text-right pr-10 h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Deep Scrutiny</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {identities.map((id) => (
                        <IdentityRow key={id.id} identity={id} onDetails={() => fetchIdentityInsights(id.id)} />
                      ))}
                      {identities.length === 0 && (
                          <TableRow>
                              <TableCell colSpan={4} className="h-40 text-center text-zinc-600 font-mono italic text-xs uppercase tracking-[0.3em]">
                                 --- Target Hub Empty. No High-Value Assets Registered ---
                              </TableCell>
                          </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </Card>
              </div>
            ) : activeView === 'dark-search' ? (
              <div className="space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                <div className="space-y-4">
                  <div className="flex items-center gap-4 text-naso-accent">
                    <Flame size={32} className="fill-current animate-pulse" />
                    <span className="text-[12px] font-black uppercase tracking-[0.6em]">Deep Web Reconnaissance Portal</span>
                  </div>
                  <h1 className="text-7xl font-black tracking-tighter text-white italic">Dark Recon Hub</h1>
                </div>

                <Card className="bg-card/40 backdrop-blur-3xl border-white/10 p-16 naso-glass shadow-[0_0_150px_rgba(0,0,0,0.8)] border-t-purple-500/20">
                  <div className="flex flex-col items-center gap-12 max-w-3xl mx-auto text-center">
                    <div className="p-8 rounded-[40px] bg-naso-accent/10 border-2 border-naso-accent/20 relative group overflow-hidden">
                        <div className="absolute inset-0 bg-naso-accent/20 blur-3xl rounded-full group-hover:blur-2xl transition-all"></div>
                        <Radar size={80} className="text-naso-accent relative z-10" />
                    </div>
                    <div className="space-y-6">
                        <h2 className="text-4xl font-black tracking-tight text-white uppercase italic">Direct Onion Intelligence Probe</h2>
                        <p className="text-zinc-500 text-base font-medium max-w-xl mx-auto leading-relaxed uppercase tracking-wider">Scrutinize encrypted historical databases and active .onion services for specific forensic identifiers.</p>
                    </div>
                    <div className="w-full flex gap-4 p-2 bg-black/40 rounded-3xl border border-white/10 focus-within:border-naso-accent/50 transition-all shadow-inner">
                        <input 
                            type="text" 
                            placeholder="Enter Signature, Email, or Hash..."
                            value={reconQuery}
                            onChange={(e) => setReconQuery(e.target.value)}
                            className="flex-1 bg-transparent px-8 font-mono text-sm text-white placeholder:text-zinc-700 outline-none"
                        />
                        <Button onClick={() => searchDarkWeb(reconQuery)} className="bg-naso-accent hover:bg-naso-accent/80 text-white font-black uppercase tracking-[0.2em] px-12 rounded-2xl h-16 shadow-2xl shadow-naso-accent/40 transition-all active:scale-95">
                            {isLoading ? <Loader2 className="animate-spin" /> : 'Launch Probe'}
                        </Button>
                    </div>
                    <div className="flex gap-8 text-[9px] font-black uppercase tracking-[0.3em] text-zinc-600">
                        <span className="flex items-center gap-2"><div className="w-1 h-1 rounded-full bg-emerald-500"></div> Ahmia Engine Active</span>
                        <span className="flex items-center gap-2"><div className="w-1 h-1 rounded-full bg-naso-accent"></div> Tor Circuit Operational</span>
                        <span className="flex items-center gap-2"><div className="w-1 h-1 rounded-full bg-naso-accent"></div> Identity Correlation On</span>
                    </div>
                  </div>
                </Card>

                {darkWebResults.length > 0 && (
                    <div className="space-y-8">
                        <div className="flex items-center justify-between border-b border-white/10 pb-6">
                            <h3 className="text-xs font-black uppercase tracking-[0.4em] text-naso-accent flex items-center gap-3">
                                <ShieldAlert size={16} /> Intercepted Intel Packages ({darkWebResults.length})
                            </h3>
                            <Button variant="ghost" className="text-[9px] font-black uppercase tracking-widest text-zinc-500 hover:text-white transition-colors">Wipe Discovery History</Button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {darkWebResults.map((res, i) => (
                                <Card key={i} className="bg-white/[0.02] border-white/5 p-8 hover:border-naso-accent/40 transition-all group naso-glass relative overflow-hidden">
                                    <div className="absolute top-0 right-0 p-8 opacity-0 group-hover:opacity-[0.05] transition-opacity pointer-events-none">
                                        <ExternalLink size={100} />
                                    </div>
                                    <div className="flex justify-between items-start mb-6">
                                        <Badge className="bg-naso-accent/10 text-naso-accent border border-naso-accent/20 font-black text-[9px] py-1 px-3">SIGNATURE MATCH FOUND</Badge>
                                        <ExternalLink size={18} className="text-zinc-600 group-hover:text-white transition-colors" />
                                    </div>
                                    <h4 className="text-xl font-black text-white mb-2 uppercase tracking-tight italic group-hover:text-naso-accent transition-colors">{res.title}</h4>
                                    <p className="text-xs font-mono text-zinc-500 break-all bg-black/40 p-4 rounded-xl border border-white/5 group-hover:border-naso-accent/20 transition-all">{res.url}</p>
                                    <div className="flex gap-3 mt-8">
                                        <Button className="flex-1 text-[10px] font-black uppercase tracking-widest bg-naso-accent/10 text-naso-accent border border-naso-accent/20 hover:bg-naso-accent/20 transition-all rounded-xl h-12">Initiate Deep Scrape</Button>
                                        <Button variant="ghost" className="text-[10px] font-black uppercase tracking-widest border border-white/5 rounded-xl h-12 px-6">Proxy Link</Button>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}
              </div>
            ) : (
              <div className="space-y-10 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                <div className="flex justify-between items-end">
                  <div className="space-y-3">
                    <h1 className="text-6xl font-black tracking-tighter text-white italic">Audit & Compliance</h1>
                    <p className="text-zinc-500 font-black uppercase tracking-[0.2em] text-[10px] max-w-2xl">Rigorous Forensic Accountability Feed. Every operation is hashed and logged in the immutable chain.</p>
                  </div>
                  <Button variant="outline" onClick={() => fetchAuditLogs()} className="border-naso-accent/40 text-naso-accent h-14 px-10 font-black uppercase text-[10px] tracking-widest rounded-2xl hover:bg-naso-accent/5 shadow-2xl transition-all">
                    <Download size={18} className="mr-3" /> Export Signed Compliance CSV
                  </Button>
                </div>

                <Card className="bg-card/20 backdrop-blur-3xl border-white/5 overflow-hidden shadow-2xl naso-glass">
                  <Table>
                    <TableHeader className="bg-white/[0.02]">
                      <TableRow className="border-white/5 h-16">
                        <TableHead className="pl-10 h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Forensic Operator & Action</TableHead>
                        <TableHead className="h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Asset Vector</TableHead>
                        <TableHead className="h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Operation Details</TableHead>
                        <TableHead className="text-right pr-10 h-16 text-[10px] font-black uppercase tracking-[0.4em] text-zinc-500">Timestamp (UTC / ISO 8601)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditLogs.map((log) => (
                        <AuditLogRow key={log.id} log={log} />
                      ))}
                      {auditLogs.length === 0 && (
                          <TableRow>
                              <TableCell colSpan={4} className="h-40 text-center text-zinc-600 font-mono italic text-xs uppercase tracking-[0.3em]">
                                 --- Scrutinizing Audit Chain... No Entries Logged ---
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
        <SheetContent className="w-[450px] sm:w-[600px] bg-[#050507]/95 border-l-naso-accent/20 backdrop-blur-3xl p-0 shadow-[-50px_0_100px_rgba(0,0,0,0.8)]">
          <SheetHeader className="p-10 border-b border-white/5 bg-gradient-to-br from-naso-accent/10 to-transparent">
            <div className="flex items-center justify-between">
                <SheetTitle className="text-3xl font-black tracking-tighter flex items-center gap-4 text-white uppercase italic"><Zap className="text-naso-accent animate-pulse" fill="currentColor" size={24} /> Intelligence Center</SheetTitle>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                    <span className="text-[10px] font-black text-red-500 uppercase tracking-widest">Live Alert Feed</span>
                </div>
            </div>
            <SheetDescription className="text-zinc-500 font-black uppercase tracking-widest text-[9px] mt-4">Critical forensic artifacts identified in the last 24 duty hours.</SheetDescription>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-8 space-y-6 scrollbar-hide">
            {leaks.filter(l => l.severity_score >= 80).map(alert => <NotificationItem key={alert.id} alert={alert} />)}
            {leaks.filter(l => l.severity_score >= 80).length === 0 && (
                 <div className="h-full flex flex-col items-center justify-center opacity-30 gap-6 text-center">
                    <ShieldCheck size={64} className="text-emerald-500" />
                    <p className="text-xs font-black uppercase tracking-[0.3em]">No Critical Threats Identified in the Current Cycle</p>
                 </div>
            )}
          </div>
          <div className="p-8 border-t border-white/5 bg-black/40">
            <Button className="w-full h-14 font-black uppercase tracking-[0.3em] text-[10px] bg-naso-accent hover:bg-naso-accent/80 text-white shadow-2xl shadow-naso-accent/30 rounded-2xl">Mark all as TRIAGED / RESOLVED</Button>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={!!selectedIdentityInsights} onOpenChange={clearSelectedIdentity}>
        <DialogContent className="max-w-5xl bg-[#050507]/98 border-naso-accent/30 backdrop-blur-3xl shadow-[0_0_200px_rgba(0,0,0,1)] overflow-hidden p-0 rounded-none">
          {selectedIdentityInsights && (
            <div className="flex flex-col h-[90vh]">
              <div className="p-12 border-b border-white/5 bg-gradient-to-br from-naso-accent/15 via-black to-transparent relative">
                <div className="absolute top-0 right-0 p-12 opacity-[0.03] pointer-events-none">
                    <Fingerprint size={200} />
                </div>
                <div className="flex items-center gap-10">
                  <div className={`p-8 rounded-[40px] bg-black/60 border-2 ${selectedIdentityInsights.identity.risk_score >= 80 ? 'border-red-500/50 shadow-[0_0_40px_rgba(239,68,68,0.2)]' : 'border-naso-accent/50 shadow-naso-glow'}`}>
                    <Users size={64} className={selectedIdentityInsights.identity.risk_score >= 80 ? 'text-red-500' : 'text-naso-accent'} />
                  </div>
                  <div className="space-y-3">
                    <h2 className="text-6xl font-black tracking-tighter text-white uppercase italic">{selectedIdentityInsights.identity.identifier}</h2>
                    <div className="flex items-center gap-8 text-[11px] font-black uppercase tracking-[0.3em] text-zinc-500">
                      <span className="flex items-center gap-2 text-naso-accent"><Fingerprint size={14} /> {selectedIdentityInsights.identity.type} MASTER PROFILE</span>
                      <span className="w-1.5 h-1.5 bg-zinc-800 rounded-full"></span>
                      <span className="flex items-center gap-2"><Clock size={14} /> LAST RECON: {new Date(selectedIdentityInsights.last_seen).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-12 space-y-12 scrollbar-hide">
                {/* Merged Profile Tree (Y) */}
                {selectedIdentityInsights.merged_identities.length > 0 && (
                  <div className="space-y-8 p-8 rounded-3xl bg-naso-accent/5 border border-naso-accent/10">
                    <div className="flex items-center justify-between">
                        <h4 className="text-xs font-black uppercase tracking-[0.4em] text-naso-accent flex items-center gap-3">
                        <Workflow size={20} className="animate-pulse" /> Neural Merged Identity Matrix
                        </h4>
                        <Badge className="bg-naso-accent text-white font-black text-[9px] px-3">{selectedIdentityInsights.merged_identities.length} NODES</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      {selectedIdentityInsights.merged_identities.map(slave => (
                        <div key={slave.id} className="p-5 rounded-2xl bg-black/40 border border-white/5 flex items-center justify-between group hover:border-naso-accent/30 transition-all">
                          <div className="flex items-center gap-4">
                            <div className="p-2 bg-naso-accent/10 rounded-lg group-hover:bg-naso-accent group-hover:text-white transition-all text-naso-accent"><UserPlus size={16} /></div>
                            <span className="text-xs font-black text-zinc-200 uppercase tracking-tight">{slave.identifier}</span>
                          </div>
                          <Badge variant="outline" className="text-[9px] border-white/10 text-zinc-500 group-hover:border-naso-accent/30 group-hover:text-naso-accent uppercase font-black">{slave.type}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  <div className="naso-glass p-8 rounded-3xl border-t-red-500/20 relative overflow-hidden group">
                    <div className="absolute -right-4 -bottom-4 p-8 opacity-[0.02] group-hover:opacity-[0.05] transition-opacity text-red-500">
                        <AlertTriangle size={100} />
                    </div>
                    <p className="text-[10px] font-black uppercase text-zinc-500 tracking-[0.3em] mb-4 flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div> Aggregated Risk Matrix
                    </p>
                    <p className={`text-6xl font-black italic tracking-tighter ${selectedIdentityInsights.identity.risk_score >= 80 ? 'text-red-500' : 'text-white'}`}>{selectedIdentityInsights.identity.risk_score}</p>
                  </div>
                  <div className="naso-glass p-8 rounded-3xl border-t-naso-accent/20 relative overflow-hidden group">
                    <div className="absolute -right-4 -bottom-4 p-8 opacity-[0.02] group-hover:opacity-[0.05] transition-opacity text-naso-accent">
                        <Database size={100} />
                    </div>
                    <p className="text-[10px] font-black uppercase text-zinc-500 tracking-[0.3em] mb-4 flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-naso-accent animate-pulse"></div> Vector Compromise Count
                    </p>
                    <p className="text-6xl font-black text-white italic tracking-tighter">{selectedIdentityInsights.total_leaks}</p>
                  </div>
                  <div className="naso-glass p-8 rounded-3xl border-t-yellow-500/20 flex flex-col justify-center">
                    <p className="text-[10px] font-black uppercase text-zinc-500 tracking-[0.3em] mb-6">Operational Priority</p>
                    <Button onClick={() => toggleIdentityProtection(selectedIdentityInsights.identity.id, !selectedIdentityInsights.identity.is_protected)} className={`w-full h-16 font-black uppercase text-[11px] tracking-[0.2em] rounded-2xl transition-all shadow-2xl ${selectedIdentityInsights.identity.is_protected ? 'bg-yellow-500 text-black shadow-yellow-500/20' : 'bg-white/5 text-white border border-white/10 hover:bg-white/10'}`}>
                      {selectedIdentityInsights.identity.is_protected ? <Lock size={18} className="mr-3" /> : <Unlock size={18} className="mr-3" />}
                      {selectedIdentityInsights.identity.is_protected ? 'SECURE VIP ASSET' : 'ELEVATE TO VIP'}
                    </Button>
                  </div>
                </div>

                <div className="space-y-8">
                  <div className="flex items-center justify-between border-b border-white/10 pb-6">
                    <h4 className="text-xs font-black uppercase tracking-[0.4em] text-zinc-400 flex items-center gap-3"><History size={20} className="text-naso-accent" /> Compromise Forensic Chronology</h4>
                    <Button variant="ghost" className="text-[9px] font-black uppercase tracking-widest text-zinc-500 hover:text-white">Expand Timeline</Button>
                  </div>
                  <div className="space-y-5">
                    {selectedIdentityInsights.leaks.map((leak) => (
                      <div key={leak.id} className="bg-white/[0.02] border border-white/5 rounded-3xl p-8 hover:border-naso-accent/30 transition-all group naso-glass relative overflow-hidden">
                        <div className="absolute top-0 right-0 h-full w-24 bg-gradient-to-l from-naso-accent/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                        <div className="flex justify-between items-center mb-6">
                          <div className="flex items-center gap-4">
                            <div className="p-3 bg-black/40 rounded-xl border border-white/5 text-zinc-400 group-hover:text-naso-accent transition-colors"><Globe size={18} /></div>
                            <div className="flex flex-col gap-1">
                                <span className="text-sm font-black text-white uppercase tracking-tight">{leak.source}</span>
                                <span className="text-[9px] font-black text-zinc-500 uppercase tracking-widest">{new Date(leak.discovered_at).toLocaleString()}</span>
                            </div>
                          </div>
                          <Badge className={`${leak.severity_score >= 80 ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-naso-accent/10 text-naso-accent border-naso-accent/20'} font-black text-[10px] py-1.5 px-4 rounded-xl border`}>PROBABILITY: {leak.severity_score}%</Badge>
                        </div>
                        <div className="p-5 rounded-2xl bg-black/40 border border-white/5 font-mono text-xs italic text-zinc-400 leading-relaxed group-hover:text-zinc-200 transition-colors">
                            {leak.content_snippet ? `[DUMP_EXTRACT]: "${leak.content_snippet}"` : '<encrypted_forensic_payload_inaccessible>'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              <div className="p-10 border-t border-white/5 bg-black/60 flex justify-end gap-5">
                <Button variant="outline" className="border-white/10 h-14 px-10 font-black uppercase tracking-widest text-[10px] rounded-2xl hover:bg-white/5" onClick={clearSelectedIdentity}>De-initialize View</Button>
                <Button className="bg-naso-accent hover:bg-naso-accent/80 text-white h-14 px-12 font-black uppercase tracking-widest text-[10px] rounded-2xl shadow-2xl shadow-naso-accent/40">
                    <Download size={18} className="mr-3" /> Generate Forensic Evidence Package
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
