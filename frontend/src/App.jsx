import React, { Suspense, lazy, useEffect, useState } from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import useNasoStore from './store/useNasoStore';
import { X, ShieldAlert, ImageIcon, Lock, Unlock, Users, Fingerprint, Clock, Workflow, UserPlus, Globe, History, Download, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Layout & Components
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import CommandMenu from './components/ui/CommandMenu';
import OnboardingTour from './components/layout/OnboardingTour';
import Toaster from './components/ui/Toaster';
import ErrorBoundary from './components/ui/ErrorBoundary';
import ProgressBar from './components/ui/ProgressBar';
import ShortcutsOverlay from './components/ui/ShortcutsOverlay';
import NotificationsSheet from './components/layout/NotificationsSheet';
import RouteFallback from './components/ui/RouteFallback';
import AuditIntegrityBanner from './components/layout/AuditIntegrityBanner';
import MergeHistorySection from './components/MergeHistorySection';
import MergePreviewDrawer from './components/MergePreviewDrawer';
import { Input, Select, Label } from './components/ui/Input';
import useTabAwareness from './lib/useTabAwareness';
import { toast } from './store/useToastStore';

// Pages — eager on the critical render path, lazy for heavy/secondary views.
// Dashboard + Login + Identities are the cold-start fast paths.
import Dashboard from './pages/Dashboard';
import Identities from './pages/Identities';
import Login from './pages/Login';

const Topology    = lazy(() => import('./pages/Topology'));
const DarkRecon   = lazy(() => import('./pages/DarkRecon'));
const Audit       = lazy(() => import('./pages/Audit'));
const AiAssistant = lazy(() => import('./components/AiAssistant'));
const DocsView    = lazy(() => import('./components/DocsView'));

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
    isLoading, systemStatus, fetchSystemStatus,
    addIdentity, updateProfile,
    graphData, fetchGraphData,
    isAuthenticated, logout,
    authChecked, fetchMe
  } = useNasoStore();

  const location = useLocation();
  const navigate = useNavigate();

  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [viewingScreenshotId, setViewingScreenshotId] = useState(null);
  const [reconQuery, setReconQuery] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // UI state for modals
  const [isAddIdentityOpen, setIsAddIdentityOpen] = useState(false);
  const [newIdentityIdentifier, setNewIdentityIdentifier] = useState('');
  const [newIdentityType, setNewIdentityType] = useState('person');

  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [editProfileEmailState, setEditProfileEmailState] = useState('');
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);

  const unacknowledgedCritical = leaks.filter(l => l.severity_score >= 80 && !l.acknowledged_at).length;

  useTabAwareness({ unacknowledged: unacknowledgedCritical, online });

  // Connection-state banner + toast. Fires once on transition, not per event.
  useEffect(() => {
    const handleOnline = () => { setOnline(true); toast.success('Connection restored', 'Intelligence feed resumed.'); };
    const handleOffline = () => { setOnline(false); toast.warning('Connection lost', 'NASO is operating from cached data.'); };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Close the mobile sidebar when the route changes (tap-through from drawer).
  useEffect(() => { setIsSidebarOpen(false); }, [location.pathname]);

  // Allow deep-link triggers from the command palette and insight chips.
  useEffect(() => {
    const onAddIdentity = () => setIsAddIdentityOpen(true);
    const onOpenNotifications = () => setIsNotificationsOpen(true);
    window.addEventListener('naso:add-identity', onAddIdentity);
    window.addEventListener('naso:open-notifications', onOpenNotifications);
    return () => {
      window.removeEventListener('naso:add-identity', onAddIdentity);
      window.removeEventListener('naso:open-notifications', onOpenNotifications);
    };
  }, []);

  // Ask the API once, on mount, whether this browser still has a session. The
  // cookie is httpOnly, so this call is the only way to find out; until it
  // answers, the auth gate below shows a restoring state rather than the login
  // form.
  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  // Power-user keyboard shortcuts. G-prefix Vim-style (g d → /, g t → /topology),
  // plus N for notifications. Ignored while typing in an input.
  useEffect(() => {
    if (!isAuthenticated) return;
    let gPending = false;
    let gTimer = null;

    const clearG = () => {
      gPending = false;
      if (gTimer) { clearTimeout(gTimer); gTimer = null; }
    };

    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return;

      const k = e.key.toLowerCase();

      if (gPending) {
        const ROUTES = { d: '/', t: '/topology', i: '/identities', r: '/dark-search', a: '/audit' };
        const target = ROUTES[k];
        if (target) {
          e.preventDefault();
          navigate(target);
        }
        clearG();
        return;
      }

      if (k === 'g') {
        gPending = true;
        gTimer = setTimeout(clearG, 900);
        return;
      }

      if (k === 'n') {
        e.preventDefault();
        setIsNotificationsOpen(v => !v);
      }
    };

    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); clearG(); };
  }, [isAuthenticated, navigate]);

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

  // Auth gate. `authChecked` distinguishes "no session" from "not asked yet":
  // the session lives in an httpOnly cookie, so the only way to know is to call
  // GET /users/me once on mount. Without this the login form rendered on every
  // page load, valid cookie or not.
  if (!authChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-zinc-500" role="status" aria-live="polite">
        <span className="animate-pulse text-sm tracking-wide">Restoring session…</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="flex h-screen bg-black text-zinc-100 overflow-hidden font-sans relative">
      {/* Skip link — visible only on keyboard focus, jumps past chrome to main content. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-[#0A84FF] focus:text-white focus:font-medium focus:text-[13px] focus:shadow-xl"
      >
        Skip to main content
      </a>

      <OnboardingTour />
      <CommandMenu />
      <Sidebar
        onEditProfile={() => setIsEditProfileOpen(true)}
        open={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <main id="main-content" role="main" aria-label="Main content" className="flex-1 flex flex-col relative overflow-hidden bg-black min-w-0">
        <AuditIntegrityBanner />
        <Header
          systemStatus={systemStatus}
          onOpenNotifications={() => setIsNotificationsOpen(true)}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          onOpenCommandMenu={() => window.dispatchEvent(new CustomEvent('naso:open-command'))}
          online={online}
        />

        {isFullHeightView ? (
          <div className="flex-1 overflow-hidden">
            <ErrorBoundary label={location.pathname === '/ai-analyst' ? 'AI Co-Analyst' : 'Docs'}>
              <Suspense fallback={<div className="p-8"><RouteFallback /></div>}>
                <Routes>
                  <Route path="/ai-analyst" element={<AiAssistant />} />
                  <Route path="/docs" element={<DocsView />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 relative scrollbar-hide">
            <div key={location.pathname} className="max-w-[1600px] mx-auto animate-route">
              <ErrorBoundary label={`Route ${location.pathname}`}>
                <Suspense fallback={<RouteFallback />}>
                  <Routes>
                    <Route path="/" element={<Dashboard setViewingScreenshotId={setViewingScreenshotId} />} />
                    <Route path="/topology" element={<ErrorBoundary label="Neural Topology"><Topology /></ErrorBoundary>} />
                    <Route path="/identities" element={<Identities openAddModal={() => setIsAddIdentityOpen(true)} />} />
                    <Route path="/dark-search" element={<DarkRecon reconQuery={reconQuery} setReconQuery={setReconQuery} />} />
                    <Route path="/audit" element={<Audit />} />
                  </Routes>
                </Suspense>
              </ErrorBoundary>
            </div>
          </div>
        )}
      </main>

      {/* Side Sheets & Dialogs */}
      <NotificationsSheet
        open={isNotificationsOpen}
        onOpenChange={setIsNotificationsOpen}
        leaks={leaks}
        acknowledgeLeak={acknowledgeLeak}
        acknowledgeAllLeaks={acknowledgeAllLeaks}
      />

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

                <MergeHistorySection identityId={selectedIdentityInsights.identity.id} />

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
              <Label htmlFor="id-identifier">Identifier / Keyword</Label>
              <Input
                id="id-identifier"
                value={newIdentityIdentifier}
                onChange={e => setNewIdentityIdentifier(e.target.value)}
                placeholder="e.g. j.doe@corp.com or handle123"
                autoFocus
              />
            </div>
            <div>
              <Label htmlFor="id-type">Asset Type</Label>
              <Select
                id="id-type"
                value={newIdentityType}
                onChange={e => setNewIdentityType(e.target.value)}
              >
                <option value="person">Person (Email / Name)</option>
                <option value="organization">Organization (Domain)</option>
                <option value="crypto">Cryptocurrency Wallet</option>
                <option value="credential">Infrastructure Credential</option>
              </Select>
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
              <Label htmlFor="profile-email">Email Address</Label>
              <Input
                id="profile-email"
                type="email"
                value={editProfileEmailState}
                onChange={e => setEditProfileEmailState(e.target.value)}
                autoFocus
                autoComplete="email"
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

      <MergePreviewDrawer />
      <ProgressBar />
      <ShortcutsOverlay />
      <Toaster />
    </div>
  );
}
