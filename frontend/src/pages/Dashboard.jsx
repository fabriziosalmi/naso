import React, { useMemo } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Shield, AlertTriangle, Users, Cpu, Activity, PieChart as PieChartIcon, Target, Download, History, Code2, MessageSquare, Globe, Image as ImageIcon, Database, Brain, ChevronRight } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';
import { StatCard } from '../components/ui/StatCard';
import { useNavigate } from 'react-router-dom';

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
        <Button onClick={() => onInspect(leak.id, false)} variant="outline" size="sm" className="h-7 text-[11px] font-medium border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 bg-transparent rounded-full px-3">
          Inspect
        </Button>
      </div>
    </TableCell>
  </TableRow>
);

const OnboardingCard = ({ icon: Icon, title, desc, onClick }) => (
  <div 
    onClick={onClick}
    className="group relative cursor-pointer flex flex-col p-8 bg-[#111111]/80 backdrop-blur-xl border border-white/[0.05] hover:border-[#0A84FF]/50 rounded-[24px] overflow-hidden transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-20px_rgba(10,132,255,0.3)]"
  >
    <div className="absolute inset-0 bg-gradient-to-b from-[#0A84FF]/0 to-[#0A84FF]/[0.02] opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
    <div className="w-12 h-12 bg-white/[0.04] rounded-2xl flex items-center justify-center mb-6 group-hover:bg-[#0A84FF]/10 transition-colors duration-500">
      <Icon size={24} className="text-zinc-400 group-hover:text-[#0A84FF] transition-colors duration-500" strokeWidth={1.5} />
    </div>
    <h3 className="text-[17px] font-semibold text-zinc-100 mb-2">{title}</h3>
    <p className="text-[14px] text-zinc-500 leading-relaxed mb-6 flex-1">{desc}</p>
    <div className="flex items-center text-[#0A84FF] text-[13px] font-medium opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
      Initialize sequence <ChevronRight size={14} className="ml-1" />
    </div>
  </div>
);

const OnboardingHero = ({ navigate }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[75vh] w-full animate-in fade-in zoom-in duration-700">
      <div className="w-20 h-20 bg-white/[0.03] rounded-[24px] border border-white/[0.08] flex items-center justify-center mb-8 shadow-2xl relative overflow-hidden">
         <div className="absolute inset-0 bg-gradient-to-br from-[#0A84FF]/20 to-transparent opacity-50" />
         <Shield size={36} className="text-[#0A84FF] relative z-10" strokeWidth={1.5} />
      </div>
      <h1 className="text-4xl font-bold tracking-tight text-white mb-4">Intelligence Core Initialized.</h1>
      <p className="text-zinc-400 text-lg max-w-xl text-center mb-16 leading-relaxed">
        NASO Forensic Engine is online and awaiting raw signals. The operational data lake is empty. Select a primary vector below to establish your intelligence baseline.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl">
        <OnboardingCard 
          icon={Globe}
          title="Sonda il Dark Web"
          desc="Lancia un probe sulla rete Tor ed estrai le prime evidenze non strutturate."
          onClick={() => navigate('/dark-search')}
        />
        <OnboardingCard 
          icon={Activity}
          title="Costruisci Grafo Neurale"
          desc="Registra un alias o una mail nel registro centrale per innescare correlazioni."
          onClick={() => navigate('/identities')}
        />
        <OnboardingCard 
          icon={Brain}
          title="Risveglia l'AI"
          desc="Apri una sessione con il Co-Analyst per familiarizzare coi tool operativi."
          onClick={() => navigate('/ai-analyst')}
        />
      </div>
    </div>
  );
};

export default function Dashboard({ setViewingScreenshotId }) {
  const { leaks, fetchLeaks, identities, exportMassiveDossier, isLoading } = useNasoStore();
  const navigate = useNavigate();

  const severityData = useMemo(() => [
    { name: 'Critical', value: leaks.filter(l => l.severity_score >= 80).length, color: '#ef4444' },
    { name: 'High', value: leaks.filter(l => l.severity_score >= 50 && l.severity_score < 80).length, color: '#f97316' },
    { name: 'Medium', value: leaks.filter(l => l.severity_score < 50).length, color: '#3b82f6' },
  ].filter(d => d.value > 0), [leaks]);

  const timelineData = useMemo(() => [...leaks]
    .sort((a, b) => new Date(a.discovered_at) - new Date(b.discovered_at))
    .reduce((acc, l) => {
      const date = new Date(l.discovered_at).toLocaleDateString();
      const existing = acc.find(d => d.date === date);
      if (existing) { existing.count += 1; } else { acc.push({ date, count: 1 }); }
      return acc;
    }, []), [leaks]);

  const isPlatformEmpty = leaks.length === 0 && identities.length === 0 && !isLoading;

  if (isPlatformEmpty) {
    return <OnboardingHero navigate={navigate} />;
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Intelligence Stream" value={leaks.length} icon={AlertTriangle} description="Detected Artifacts"  trend="up" trendValue="24" />
        <StatCard title="Critical Breaches" value={leaks.filter(l => l.severity_score >= 80).length} icon={Target} description="High-Impact Recon" trend="up" trendValue="18"  />
        <StatCard title="Active Targets" value={identities.length} icon={Users} description="Monitored Assets" trend="down" trendValue="4" />
        <StatCard title="Infrastructure Load" value="18.4%" icon={Cpu} description="Worker Cluster Utilization" trend="down" trendValue="2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
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

      <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden shadow-sm relative rounded-2xl mt-8">
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
                  <History size={14} className="mr-2" strokeWidth={1.5} /> Sync Intelligence
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
                  if (isScreenshot) setViewingScreenshotId(id);
                  else navigate('/identities');
                }} 
              />
            ))}
            {isLoading && (
                <TableRow>
                    <TableCell colSpan={5} className="h-40 text-center text-zinc-500 font-mono text-xs uppercase tracking-[0.3em]">
                       <div className="flex items-center justify-center gap-3">
                         <div className="w-2 h-2 bg-[#0A84FF] rounded-full animate-ping"></div>
                         Syncing Intelligence Matrix...
                       </div>
                    </TableCell>
                </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </>
  );
}
