import React, { useEffect, useState } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import useNasoStore from './store/useNasoStore';
import { ShieldCheck, Zap, X, ShieldAlert, ImageIcon, Lock, Unlock, Users, Fingerprint, Clock, Workflow, UserPlus, Globe, History, Download, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Layout & Components
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import AiAssistant from './components/AiAssistant';
import DocsView from './components/DocsView';
import CommandMenu from './components/ui/CommandMenu';
import OnboardingTour from './components/layout/OnboardingTour';

// Pages
import Dashboard from './pages/Dashboard';
import Topology from './pages/Topology';
import Identities from './pages/Identities';
import DarkRecon from './pages/DarkRecon';
import Audit from './pages/Audit';
import Login from './pages/Login';

const NotificationItem = ({ alert, onAck }) => (
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

const ScreenshotLightbox = ({ leakId, leaks, onClose }) => {
  const { fetchScreenshot } = useNasoStore();
  const leak = leaks.find(l => l.id === leakId);
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
  }, [leakId, fetchScreenshot]);

  return (
    <Dialog open={!!leakId} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl bg-[#1C1C1E]/98 border-white/[0.08] p-0 overflow-hidden backdrop-blur-3xl rounded-2xl shadow-2xl">
        <div className="relative aspect-video w-full bg-black/60 flex items-center justify-center">
          {loading ? (
            <div className="flex flex-col items-center gap-4">
              <Loader2 size={36} className="animate-spin text-[#0A84FF]" strokeWidth={1.5} />
              <p className="text-[12px] text-zinc-500">Loading forensic artifact...</p>
            </div>
          ) : imgUrl ? (
            <div className="relative w-full h-full p-8">
                <img 
                    src={imgUrl} 
                    alt="Forensic Evidence"
                    className="w-full h-full object-contain rounded-xl"
                />
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 text-zinc-600">
                <ShieldAlert size={36} strokeWidth={1.5} />
                <p className="text-[13px] text-zinc-500">Artifact unavailable or access denied</p>
            </div>
          )}
          <div className="absolute top-0 left-0 w-full p-5 flex justify-between items-center bg-gradient-to-b from-black/80 to-transparent z-10">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[#0A84FF]/10 border border-[#0A84FF]/20 rounded-lg">
                <ImageIcon size={16} className="text-[#0A84FF]" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-[11px] text-zinc-400">Forensic Evidence</p>
                <p className="text-[13px] font-medium text-white tracking-tight">Artifact: {leakId?.slice(0,8).toUpperCase()}</p>
              </div>
            </div>
            <div className="flex gap-2">
                <Button variant="ghost" size="icon" onClick={onClose} className="text-zinc-400 hover:text-white hover:bg-white/10 h-8 w-8 rounded-full transition-all"><X size={16} /></Button>
            </div>
          </div>
          <div className="absolute bottom-4 right-4 px-3 py-2 rounded-xl bg-black/60 border border-white/[0.06] space-y-1">
             <p className="text-[10px] text-zinc-500 font-mono">SHA256: {leak?.metadata_json?.sha256 || leakId?.slice(0,16).toUpperCase() || 'unknown'}</p>
             <p className="text-[10px] text-zinc-500 font-mono">{leak?.discovered_at ? new Date(leak.discovered_at).toLocaleString() : new Date().toISOString()}</p>
             <Badge className={`w-full justify-center text-[10px] font-medium ${leak?.acknowledged_at ? 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20' : 'bg-[#32D74B]/10 text-[#32D74B] border-[#32D74B]/20'}`}>
               {leak?.acknowledged_at ? 'ACKNOWLEDGED' : 'UNMODIFIED'}
             </Badge>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default function App() {
  const {
    leaks, fetchLeaks, acknowledgeLeak, acknowledgeAllLeaks,
    identities, fetchIdentities,
    auditLogs, fetchAuditLogs,
    selectedIdentityInsights, clearSelectedIdentity,
    toggleIdentityProtection,
    isLoading, systemStatus, fetchSystemStatus, error, clearError,
    addIdentity, updateProfile,
    graphData, fetchGraphData,
    isAuthenticated, logout
  } = useNasoStore();

  const location = useLocation();

  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [viewingScreenshotId, setViewingScreenshotId] = useState(null);
  const [reconQuery, setReconQuery] = useState('');

  // UI state for modals
  const [isAddIdentityOpen, setIsAddIdentityOpen] = useState(false);
  const [newIdentityIdentifier, setNewIdentityIdentifier] = useState('');
  const [newIdentityType, setNewIdentityType] = useState('person');

  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [editProfileEmailState, setEditProfileEmailState] = useState('');

  useEffect(() => {
    fetchLeaks();
    fetchSystemStatus();
    fetchIdentities({ only_masters: true });
    
    // Initial fetch based on route if necessary
    if (location.pathname === '/audit') fetchAuditLogs();
    if (location.pathname === '/topology') fetchGraphData();
    
    const interval = setInterval(() => {
      fetchLeaks();
      fetchSystemStatus();
      if (location.pathname === '/identities') fetchIdentities({ only_masters: true });
      if (location.pathname === '/audit') fetchAuditLogs();
      if (location.pathname === '/topology') fetchGraphData();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchLeaks, fetchSystemStatus, fetchIdentities, fetchAuditLogs, fetchGraphData, location.pathname]);

  const isFullHeightView = ['/ai-analyst', '/docs'].includes(location.pathname);

  // Auth gate: show login if not authenticated
  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="flex h-screen bg-black text-zinc-100 overflow-hidden font-sans relative">
      <OnboardingTour />
      <CommandMenu />
      <Sidebar onEditProfile={() => setIsEditProfileOpen(true)} />

      <main className="flex-1 flex flex-col relative overflow-hidden bg-black">
        <Header systemStatus={systemStatus} onOpenNotifications={() => setIsNotificationsOpen(true)} />

        {isFullHeightView ? (
          <div className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/ai-analyst" element={<AiAssistant />} />
              <Route path="/docs" element={<DocsView />} />
            </Routes>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-8 relative scrollbar-hide">
            <div className="max-w-[1600px] mx-auto">
              <Routes>
                <Route path="/" element={<Dashboard setViewingScreenshotId={setViewingScreenshotId} />} />
                <Route path="/topology" element={<Topology />} />
                <Route path="/identities" element={<Identities openAddModal={() => setIsAddIdentityOpen(true)} />} />
                <Route path="/dark-search" element={<DarkRecon reconQuery={reconQuery} setReconQuery={setReconQuery} />} />
                <Route path="/audit" element={<Audit />} />
              </Routes>
            </div>
          </div>
        )}
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
            {leaks.filter(l => l.severity_score >= 80).map(alert => <NotificationItem key={alert.id} alert={alert} onAck={acknowledgeLeak} />)}
            {leaks.filter(l => l.severity_score >= 80).length === 0 && (
                 <div className="h-48 flex flex-col items-center justify-center text-zinc-600 gap-4">
                    <ShieldCheck size={36} className="text-[#32D74B]" strokeWidth={1.5} />
                    <p className="text-[13px] font-medium text-zinc-500">No critical threats identified</p>
                 </div>
            )}
          </div>
          <div className="p-5 border-t border-white/[0.08]">
            <Button
              className="w-full h-10 font-medium text-[13px] bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full"
              onClick={() => acknowledgeAllLeaks()}
            >
              Mark All as Resolved
            </Button>
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
      <ScreenshotLightbox leakId={viewingScreenshotId} leaks={leaks} onClose={() => setViewingScreenshotId(null)} />

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
