import { create } from 'zustand';
import axios from 'axios';
import { toast } from './useToastStore';

// Tutti i request axios inviano automaticamente il cookie httpOnly naso_access_token
axios.defaults.withCredentials = true;

// CSRF double-submit cookie. The backend issues a non-httpOnly `naso_csrf`
// cookie at login; we read it with document.cookie and echo it back as
// X-Naso-CSRF on every state-changing request. Safe methods skip — the
// middleware itself short-circuits GET/HEAD/OPTIONS, so we don't bother
// the network with a header it would ignore.
const CSRF_COOKIE_NAME = 'naso_csrf';
const CSRF_HEADER_NAME = 'X-Naso-CSRF';
const SAFE_METHODS = new Set(['get', 'head', 'options']);

export function readCsrfToken() {
  if (typeof document === 'undefined' || !document.cookie) return null;
  const prefix = `${CSRF_COOKIE_NAME}=`;
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length));
  }
  return null;
}

axios.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase();
  if (SAFE_METHODS.has(method)) return config;
  const token = readCsrfToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers[CSRF_HEADER_NAME] = token;
  }
  return config;
});

const useNasoStore = create((set, get) => ({
  user: null,
  isAuthenticated: false,
  // True once we've asked the backend whether the httpOnly cookie is still
  // valid. The SPA blocks routing on this so a hard refresh doesn't flash
  // <Login /> for a frame before the session-restore call resolves.
  authChecked: false,
  token: null,
  leaks: [],
  identities: [],
  auditLogs: [],
  auditTotal: 0,    // Total rows the server has, regardless of the current page.
  darkWebResults: [],
  graphData: { nodes: [], links: [] },
  selectedIdentityInsights: null,
  systemStatus: null,
  isLoading: false,
  error: null,

  // ── AI Co-Analyst state ──────────────────────────────────────────
  chatHistory: [],          // { role, content, toolCalls?, toolResults?, id }
  investigations: [],       // list of InvestigationPlan objects
  activeInvestigationId: null,
  isAiStreaming: false,
  aiStatus: null,           // null | 'online' | 'offline'
  evidencePanel: [],        // tool results shown in right panel

  // Check if local AI is reachable
  checkAiHealth: async () => {
    try {
      const res = await axios.get('/ai/health');
      set({ aiStatus: res.data.status });
      return res.data;
    } catch {
      set({ aiStatus: 'offline' });
      return { status: 'offline' };
    }
  },

  // Stream a message to the AI Co-Analyst
  sendAiMessage: async (content) => {
    const { isAuthenticated, chatHistory, activeInvestigationId } = get();
    if (!isAuthenticated || !content.trim()) return;

    const userMsg = { id: Date.now().toString(), role: 'user', content };
    const history = [...chatHistory, userMsg];
    set({ chatHistory: history, isAiStreaming: true, error: null });

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg = { id: assistantMsgId, role: 'assistant', content: '', toolCalls: [], toolResults: [] };
    set(state => ({ chatHistory: [...state.chatHistory, assistantMsg] }));

    const maxRetries = 5;
    let attempt = 0;
    
    while (attempt < maxRetries) {
      try {
        // fetch() bypasses the axios interceptor, so we attach the CSRF
        // token by hand. The auth cookie rides via credentials: 'include'.
        const csrfToken = readCsrfToken();
        const response = await fetch('/ai/chat', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}),
          },
          body: JSON.stringify({
            messages: history.map(m => ({ role: m.role, content: m.content })),
            investigation_id: activeInvestigationId,
          }),
        });

        if (!response.ok) {
          if (response.status === 401) {
            get().logout();
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop(); // Keep incomplete line

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const raw = line.slice(6).trim();
            if (raw === '[DONE]') break;

            try {
              const event = JSON.parse(raw);

              if (event.type === 'text') {
                set(state => {
                  const msgs = [...state.chatHistory];
                  const idx = msgs.findIndex(m => m.id === assistantMsgId);
                  if (idx !== -1) msgs[idx] = { ...msgs[idx], content: msgs[idx].content + event.content };
                  return { chatHistory: msgs };
                });
              } else if (event.type === 'tool_call') {
                set(state => {
                  const msgs = [...state.chatHistory];
                  const idx = msgs.findIndex(m => m.id === assistantMsgId);
                  if (idx !== -1) {
                    msgs[idx] = { ...msgs[idx], toolCalls: [...(msgs[idx].toolCalls || []), event] };
                  }
                  return { chatHistory: msgs };
                });
              } else if (event.type === 'tool_result') {
                set(state => {
                  const msgs = [...state.chatHistory];
                  const idx = msgs.findIndex(m => m.id === assistantMsgId);
                  if (idx !== -1) {
                    msgs[idx] = { ...msgs[idx], toolResults: [...(msgs[idx].toolResults || []), event] };
                  }
                  return {
                    chatHistory: msgs,
                    evidencePanel: [event, ...state.evidencePanel].slice(0, 20),
                  };
                });
                // Refresh investigations if a task was created
                if (event.name === 'create_task') get().fetchInvestigations();
              } else if (event.type === 'error') {
                set(state => {
                  const msgs = [...state.chatHistory];
                  const idx = msgs.findIndex(m => m.id === assistantMsgId);
                  if (idx !== -1) msgs[idx] = { ...msgs[idx], content: `⚠️ ${event.message}`, isError: true };
                  return { chatHistory: msgs };
                });
              }
            } catch { /* Skip malformed SSE lines */ }
          }
        }
        // Success breaks the retry loop
        break; 
      } catch (err) {
        attempt++;
        if (attempt >= maxRetries) {
          set(state => {
            const msgs = [...state.chatHistory];
            const idx = msgs.findIndex(m => m.id === assistantMsgId);
            if (idx !== -1) msgs[idx] = { ...msgs[idx], content: `⚠️ Connection permanently failed after ${maxRetries} retries: ${err.message}`, isError: true };
            return { chatHistory: msgs };
          });
          break;
        } else {
          // Exponential backoff + Jitter
          const backoff = Math.min(1000 * Math.pow(2, attempt) + Math.random() * 500, 10000);
          console.warn(`[SSE Stream] Reconnecting... Attempt ${attempt}/${maxRetries} in ${backoff}ms`);
          await new Promise(r => setTimeout(r, backoff));
        }
      }
    }
    
    set({ isAiStreaming: false });
  },

  clearChatHistory: () => set({ chatHistory: [], evidencePanel: [] }),

  // Investigation Plans
  fetchInvestigations: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const res = await axios.get('/ai/plans');
      set({ investigations: res.data });
    } catch { /* silent */ }
  },

  createInvestigation: async (title, description) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const res = await axios.post('/ai/plans', { title, description });
      set(state => ({ investigations: [res.data, ...state.investigations], activeInvestigationId: res.data.id }));
      return res.data;
    } catch (err) {
      set({ error: 'Failed to create investigation plan' });
    }
  },

  updateInvestigation: async (planId, updates) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.patch(`/ai/plans/${planId}`, updates);
      get().fetchInvestigations();
    } catch { /* silent */ }
  },

  deleteInvestigation: async (planId) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.delete(`/ai/plans/${planId}`);
      set(state => ({
        investigations: state.investigations.filter(p => p.id !== planId),
        activeInvestigationId: state.activeInvestigationId === planId ? null : state.activeInvestigationId,
      }));
    } catch { /* silent */ }
  },

  addTaskToInvestigation: async (planId, content) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.post(`/ai/plans/${planId}/tasks`, { content });
      get().fetchInvestigations();
    } catch { /* silent */ }
  },

  updateTask: async (planId, taskId, updates) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.patch(`/ai/plans/${planId}/tasks/${taskId}`, updates);
      get().fetchInvestigations();
    } catch { /* silent */ }
  },

  setActiveInvestigation: (id) => set({ activeInvestigationId: id }),
  clearEvidencePanel: () => set({ evidencePanel: [] }),

  fetchSystemStatus: async () => {
    try {
      const response = await axios.get('/system/status');
      set({ systemStatus: response.data });
    } catch (err) {
      set({ systemStatus: { status: 'offline', latency_ms: { total: 0 } } });
    }
  },

  // Auth Actions
  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);
      
      await axios.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      // Il backend imposta il cookie httpOnly — nessun token da memorizzare in JS
      set({ isAuthenticated: true, authChecked: true, isLoading: false });
    } catch (err) {
      set({ error: 'Authentication failed', isLoading: false });
    }
  },

  logout: async () => {
    try {
      await axios.post('/auth/logout'); // Il backend cancella il cookie
    } catch { /* ignora errori di rete — il logout locale avviene sempre */ }
    set({ user: null, isAuthenticated: false, authChecked: true, token: null, leaks: [], identities: [], auditLogs: [], darkWebResults: [] });
    toast.info('Signed out', 'Session terminated.');
  },

  // Leaks Actions
  fetchLeaks: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    
    set({ isLoading: true });
    try {
      const response = await axios.get('/leaks/');
      set({ leaks: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to retrieve intelligence data', isLoading: false });
    }
  },

  // Identity Actions (Q)
  addIdentity: async (identifier, type) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Not authenticated' });
    set({ isLoading: true });
    try {
      await axios.post('/identities/', { identifier, type });
      get().fetchIdentities();
      get().fetchAuditLogs();
      set({ isLoading: false });
      toast.success('Identity registered', `${identifier} is now monitored.`);
    } catch (err) {
      set({ error: 'Failed to register identity', isLoading: false });
      toast.error('Registration failed', 'Could not add identity to the ledger.');
    }
  },
  
  fetchIdentities: async (params = {}) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      const response = await axios.get('/identities/', { params });
      set({ identities: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to load identities', isLoading: false });
    }
  },

  triggerIdentityMerging: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      await axios.post('/identities/merge', {});
      get().fetchIdentities();
      get().fetchAuditLogs();
      get().fetchGraphData();
      set({ isLoading: false });
      toast.success('Auto-merge complete', 'Identity graph reconciled.');
    } catch (err) {
      set({ error: 'Auto-merge failed. Check logs.', isLoading: false });
      toast.error('Auto-merge failed', 'Correlation engine returned an error.');
    }
  },


  fetchIdentityInsights: async (identityId) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      const response = await axios.get(`/identities/${identityId}/insights`);
      set({ selectedIdentityInsights: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to load identity details', isLoading: false });
    }
  },

  toggleIdentityProtection: async (identityId, isProtected) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.patch(`/identities/${identityId}/protect`, { is_protected: isProtected });
      get().fetchIdentities();
      get().fetchAuditLogs();
      if (get().selectedIdentityInsights?.identity.id === identityId) {
        get().fetchIdentityInsights(identityId);
      }
      toast.success(
        isProtected ? 'Marked as VIP' : 'VIP protection removed',
        isProtected ? 'Asset escalated to protected tier.' : 'Asset returned to standard tier.'
      );
    } catch (err) {
      set({ error: 'Failed to update identity protection' });
      toast.error('Update failed', 'Could not change protection tier.');
    }
  },

  // Dark Web Search (AA) — now receives the full report shape:
  // { results, pages_fetched, duplicates_dropped, elapsed_seconds, cached, rotation, query }
  darkWebReport: null,
  searchDarkWeb: async (query) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Authentication required' });
    if (!query || !query.trim()) return set({ error: 'Enter a search query before launching probe' });
    set({ isLoading: true, error: null, darkWebResults: [], darkWebReport: null });
    try {
      const response = await axios.get('/leaks/recon/darkweb', { params: { q: query.trim() } });
      const report = response.data ?? {};
      const results = Array.isArray(report) ? report : report.results ?? [];
      set({
        darkWebResults: results,
        darkWebReport: Array.isArray(report) ? null : report,
        isLoading: false,
      });
      get().fetchAuditLogs();
      const n = results.length;
      if (n > 0) {
        const suffix = report.cached ? ' (from cache)' : '';
        toast.success('Probe complete', `${n} artifact${n === 1 ? '' : 's'} intercepted${suffix}.`);
      } else {
        toast.info('Probe complete', 'No dark-web matches for this signature.');
      }
    } catch (err) {
      set({ error: 'Dark Web probe failed — check backend connectivity', isLoading: false });
      toast.error('Probe failed', 'Tor circuit or Ahmia gateway unreachable.');
    }
  },

  // ── Correlation engine v2: merges + audit verify ──────────────────────
  mergeEvents: [],
  mergePreview: null,
  identityMergeHistory: {},  // map: identity_id → list of events

  fetchRecentMerges: async (limit = 50) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const res = await axios.get('/identities/merges', { params: { limit } });
      set({ mergeEvents: res.data });
      return res.data;
    } catch (err) {
      set({ error: 'Failed to load merge history' });
    }
  },

  fetchIdentityMergeHistory: async (identityId) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated || !identityId) return;
    try {
      const res = await axios.get(`/identities/${identityId}/merges`);
      set(state => ({
        identityMergeHistory: { ...state.identityMergeHistory, [identityId]: res.data },
      }));
      return res.data;
    } catch (err) {
      set({ error: 'Failed to load identity merge history' });
    }
  },

  fetchMergePreview: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      const res = await axios.get('/identities/merge/preview');
      set({ mergePreview: res.data, isLoading: false });
      return res.data;
    } catch (err) {
      set({ error: 'Failed to load merge preview', isLoading: false });
      toast.error('Preview failed', 'Could not compute merge candidates.');
    }
  },

  executeSelectedMerges: async (pairs) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated || !pairs?.length) return null;
    try {
      const res = await axios.post('/identities/merge/execute', { pairs });
      const { merged, skipped_weak, skipped_invariant, skipped_no_evidence } = res.data;
      const mergedCount = merged?.length ?? 0;
      const skippedCount =
        (skipped_weak?.length ?? 0) +
        (skipped_invariant?.length ?? 0) +
        (skipped_no_evidence?.length ?? 0);

      if (mergedCount > 0) {
        toast.success(
          `${mergedCount} merge${mergedCount === 1 ? '' : 's'} executed`,
          skippedCount > 0 ? `${skippedCount} pair${skippedCount === 1 ? '' : 's'} skipped — see drawer.` : 'Identity graph reconciled.'
        );
      } else if (skippedCount > 0) {
        toast.warning('No merges executed', `${skippedCount} pair${skippedCount === 1 ? '' : 's'} did not meet the merge criteria.`);
      }

      // Refresh preview + identities so the UI reflects the new graph.
      get().fetchMergePreview();
      get().fetchIdentities();
      get().fetchRecentMerges();
      return res.data;
    } catch (err) {
      toast.error('Merge execution failed', err?.response?.data?.detail ?? 'Could not execute selected merges.');
    }
  },

  // Drawer open/close (controlled from Cmd+K + menu triggers).
  mergePreviewDrawerOpen: false,
  openMergePreviewDrawer: async () => {
    set({ mergePreviewDrawerOpen: true });
    await get().fetchMergePreview();
  },
  closeMergePreviewDrawer: () => set({ mergePreviewDrawerOpen: false }),

  reverseMerge: async (eventId, reason) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    if (!reason || !reason.trim()) return toast.error('Reason required', 'Provide a reason for the reversal.');
    try {
      await axios.post(`/identities/merges/${eventId}/reverse`, { reason: reason.trim() });
      toast.success('Merge reversed', 'Slave identity restored to independent.');
      // Refresh any merge-history view we might be showing.
      get().fetchRecentMerges();
      const current = get().selectedIdentityInsights?.identity?.id;
      if (current) {
        get().fetchIdentityInsights(current);
        get().fetchIdentityMergeHistory(current);
      }
      get().fetchIdentities();
    } catch (err) {
      const msg = err?.response?.data?.detail ?? 'Reverse failed';
      toast.error('Reverse failed', msg);
    }
  },

  verifyAuditChain: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const res = await axios.get('/system/audit/verify');
      const { ok, broken_at, reason, total } = res.data;
      if (ok) {
        toast.success('Audit chain intact', `${total} entries verified · hash chain valid.`);
      } else {
        toast.error('Audit chain broken', `Row ${broken_at}: ${reason ?? 'integrity mismatch'}`);
      }
      return res.data;
    } catch (err) {
      toast.error('Verification failed', 'Could not reach audit verification endpoint.');
    }
  },

  // ── Audit integrity banner state ───────────────────────────────────────
  // Shape: { ok, broken_at, reason, total, tenant_id, checkedAt, error? }.
  // ``checkedAt`` is the local ``Date.now()`` at fetch time so the 5-minute
  // TTL check does not depend on a monotonic server clock. ``error`` is
  // set when the verify endpoint itself errors (network / 500), distinct
  // from a clean ``ok=false`` answer.
  auditIntegrity: null,
  AUDIT_INTEGRITY_TTL_MS: 5 * 60 * 1000,

  refreshAuditIntegrity: async ({ force = false } = {}) => {
    const { isAuthenticated, auditIntegrity, AUDIT_INTEGRITY_TTL_MS } = get();
    if (!isAuthenticated) return;
    if (
      !force &&
      auditIntegrity?.checkedAt &&
      Date.now() - auditIntegrity.checkedAt < AUDIT_INTEGRITY_TTL_MS
    ) {
      return auditIntegrity; // TTL cache — background checks on every route change become free.
    }
    try {
      const res = await axios.get('/system/audit/verify');
      const snapshot = { ...res.data, checkedAt: Date.now(), error: null };
      set({ auditIntegrity: snapshot });
      return snapshot;
    } catch (err) {
      const snapshot = {
        ok: null, // null (not false) so the banner can distinguish "unknown" from "broken"
        broken_at: null,
        reason: null,
        total: null,
        checkedAt: Date.now(),
        error: err?.message || 'verification request failed',
      };
      set({ auditIntegrity: snapshot });
      return snapshot;
    }
  },

  // Telegram Intelligence (Manual Probe)
  searchTelegram: async (query) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Authentication required' });
    if (!query || !query.trim()) return set({ error: 'Enter a search query before launching probe' });
    set({ isLoading: true, error: null });
    try {
      await axios.get('/leaks/recon/telegram', { params: { channel: query.trim() } });
      get().fetchLeaks();
      get().fetchAuditLogs();
      set({ isLoading: false });
    } catch (err) {
      set({ error: 'Telegram intercept failed — check backend connectivity', isLoading: false });
    }
  },

  // Shodan Recon (Manual Probe)
  searchShodan: async (ip) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Authentication required' });
    if (!ip || !ip.trim()) return set({ error: 'Enter an IP address before launching probe' });
    set({ isLoading: true, error: null });
    try {
      await axios.get('/leaks/recon/shodan', { params: { ip: ip.trim() } });
      get().fetchIdentities();
      get().fetchAuditLogs();
      set({ isLoading: false });
    } catch (err) {
      set({ error: 'Shodan scan failed — ensure API key is configured', isLoading: false });
    }
  },

  // Massive Export (BB)
  exportMassiveDossier: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    let url = null;
    let link = null;
    try {
      const response = await axios.get('/leaks/export/dossier', { responseType: 'blob' });
      // The blob URL is held by the browser until revoked; without the
      // cleanup below every dossier export leaked a few MB. Same goes
      // for the <a> we synthesize — leaving it in the DOM was harmless
      // but accumulating.
      url = window.URL.createObjectURL(new Blob([response.data]));
      link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'NASO-FULL-DOSSIER.pdf');
      document.body.appendChild(link);
      link.click();
      get().fetchAuditLogs();
      toast.success('Dossier exported', 'NASO-FULL-DOSSIER.pdf downloaded.');
    } catch (err) {
      set({ error: 'Dossier export failed' });
      toast.error('Export failed', 'Could not compile the forensic dossier.');
    } finally {
      // Always clean up, including on error after createObjectURL.
      if (link && link.parentNode) link.parentNode.removeChild(link);
      if (url) window.URL.revokeObjectURL(url);
    }
  },

  // System & Compliance Actions (#10)
  updateProfile: async (email) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Not authenticated' });
    set({ isLoading: true });
    try {
      await axios.put('/users/me', { email });
      get().fetchAuditLogs();
      set({ isLoading: false });
      toast.success('Profile updated', 'Operator credentials saved.');
    } catch (err) {
      set({ error: 'Profile update failed', isLoading: false });
      toast.error('Update failed', 'Could not save profile changes.');
    }
  },

  fetchAuditLogs: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      const response = await axios.get('/system/audit');
      const data = response.data;
      // Backend returns {total, limit, offset, items}; older deployments
      // (or callers that haven't upgraded) might still hand back a bare
      // array. Accept both so a partial roll-out doesn't blank the UI.
      if (Array.isArray(data)) {
        set({ auditLogs: data, auditTotal: data.length, isLoading: false });
      } else {
        set({
          auditLogs: data.items || [],
          auditTotal: data.total ?? 0,
          isLoading: false,
        });
      }
    } catch (err) {
      set({ error: "Audit log fetch failed", isLoading: false });
      console.error("Audit log fetch failed", err);
    }
  },

  exportAuditCsv: () => {
    const { auditLogs } = get();
    if (!auditLogs || auditLogs.length === 0) return;

    // CSV injection mitigation. A cell starting with =, +, -, @, \t, or
    // \r is parsed as a formula by Excel / LibreOffice / Google Sheets.
    // Audit log fields like ``action`` or ``resource_type`` come from
    // user input upstream — an attacker who registered an "identity"
    // named ``=cmd|'/c calc'!A1`` would otherwise own every analyst
    // who opens the export. Prefixing with a single quote forces text
    // mode in every spreadsheet client that matters; the quote itself
    // doesn't render. See OWASP "CSV Injection" cheat sheet.
    const csvSafe = (v) => {
      const s = v == null ? '' : String(v);
      if (s && /^[=+\-@\t\r]/.test(s)) return "'" + s;
      return s;
    };
    // Escape embedded double quotes per RFC 4180 ("" inside a quoted
    // field). Apply *after* csvSafe so the leading quote we add is
    // counted as a normal character.
    const csvField = (v) => `"${csvSafe(v).replace(/"/g, '""')}"`;

    const headers = ['Timestamp', 'Operator', 'Action', 'Asset Vector', 'Details'];
    const rows = auditLogs.map(log => [
      log.timestamp,
      log.user_id,
      log.action,
      log.resource_type || '',
      log.details ? JSON.stringify(log.details) : ''
    ]);

    const csvContent = headers.join(',') + '\n' +
      rows.map(e => e.map(csvField).join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'NASO-AUDIT-LOG.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },


  fetchGraphData: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const response = await axios.get('/identities/graph');
      set({ graphData: response.data });
    } catch (err) {
      set({ error: "Graph fetch failed" });
      console.error("Graph fetch failed", err);
    }
  },

  fetchScreenshot: async (leakId) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return null;
    try {
      const response = await axios.get(`/leaks/${leakId}/screenshot`, { responseType: 'blob' });
      return URL.createObjectURL(response.data);
    } catch (err) {
      set({ error: "Screenshot fetch failed" });
      console.error("Screenshot fetch failed", err);
      return null;
    }
  },

  clearSelectedIdentity: () => set({ selectedIdentityInsights: null }),
  clearError: () => set({ error: null }),

  acknowledgeLeak: async (leakId) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      await axios.patch(`/leaks/${leakId}/ack`, {});
      set(state => ({
        leaks: state.leaks.map(l =>
          l.id === leakId ? { ...l, acknowledged_at: new Date().toISOString() } : l
        )
      }));
      toast.success('Alert acknowledged');
    } catch {
      set({ error: 'Failed to acknowledge alert' });
      toast.error('Acknowledge failed');
    }
  },

  acknowledgeAllLeaks: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    try {
      const res = await axios.post('/leaks/ack-all', { min_severity: 80 });
      const acknowledgedIds = new Set(
        get().leaks
          .filter(l => l.severity_score >= 80 && !l.acknowledged_at)
          .map(l => l.id)
      );
      const now = new Date().toISOString();
      set(state => ({
        leaks: state.leaks.map(l =>
          acknowledgedIds.has(l.id) ? { ...l, acknowledged_at: now } : l
        )
      }));
      const n = res.data?.acknowledged_count ?? acknowledgedIds.size;
      toast.success('Alerts resolved', `${n} critical alert${n === 1 ? '' : 's'} acknowledged.`);
      return n;
    } catch {
      set({ error: 'Failed to acknowledge alerts' });
      toast.error('Bulk acknowledge failed');
    }
  },

  fetchMe: async () => {
    try {
      const res = await axios.get('/users/me');
      set({ user: res.data, isAuthenticated: true, authChecked: true });
    } catch {
      // 401 (no/expired cookie) is the steady-state for an anonymous
      // visitor — keep silent. authChecked flips either way so the SPA
      // can finish the boot decision.
      set({ isAuthenticated: false, user: null, authChecked: true });
    }
  },
}));

export default useNasoStore;
