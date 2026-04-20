import { create } from 'zustand';
import axios from 'axios';

// Tutti i request axios inviano automaticamente il cookie httpOnly naso_access_token
axios.defaults.withCredentials = true;

const useNasoStore = create((set, get) => ({
  user: null,
  isAuthenticated: false,
  leaks: [],
  identities: [],
  auditLogs: [],
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
        const response = await fetch('/ai/chat', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
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
      set({ isAuthenticated: true, isLoading: false });
    } catch (err) {
      set({ error: 'Authentication failed', isLoading: false });
    }
  },

  logout: async () => {
    try {
      await axios.post('/auth/logout'); // Il backend cancella il cookie
    } catch { /* ignora errori di rete — il logout locale avviene sempre */ }
    set({ user: null, isAuthenticated: false, leaks: [], identities: [], auditLogs: [], darkWebResults: [] });
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
    } catch (err) {
      set({ error: 'Failed to register identity', isLoading: false });
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
    } catch (err) {
      set({ error: 'Auto-merge failed. Check logs.', isLoading: false });
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
    } catch (err) {
      set({ error: 'Failed to update identity protection' });
    }
  },

  // Dark Web Search (AA)
  searchDarkWeb: async (query) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Authentication required' });
    if (!query || !query.trim()) return set({ error: 'Enter a search query before launching probe' });
    set({ isLoading: true, error: null, darkWebResults: [] });
    try {
      const response = await axios.get('/leaks/recon/darkweb', { params: { q: query.trim() } });
      set({ darkWebResults: response.data, isLoading: false });
      get().fetchAuditLogs();
    } catch (err) {
      set({ error: 'Dark Web probe failed — check backend connectivity', isLoading: false });
    }
  },

  // Telegram Intelligence (Manual Probe)
  searchTelegram: async (query) => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return set({ error: 'Authentication required' });
    if (!query || !query.trim()) return set({ error: 'Enter a search query before launching probe' });
    set({ isLoading: true, error: null });
    try {
      await axios.get('/leaks/recon/telegram', { params: { channel_username: query.trim() } });
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
    try {
      const response = await axios.get('/leaks/export/dossier', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'NASO-FULL-DOSSIER.pdf');
      document.body.appendChild(link);
      link.click();
      get().fetchAuditLogs();
    } catch (err) {
      set({ error: 'Dossier export failed' });
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
    } catch (err) {
      set({ error: 'Profile update failed', isLoading: false });
    }
  },

  fetchAuditLogs: async () => {
    const { isAuthenticated } = get();
    if (!isAuthenticated) return;
    set({ isLoading: true });
    try {
      const response = await axios.get('/system/audit');
      set({ auditLogs: response.data, isLoading: false });
    } catch (err) {
      set({ error: "Audit log fetch failed", isLoading: false });
      console.error("Audit log fetch failed", err);
    }
  },

  exportAuditCsv: () => {
    const { auditLogs } = get();
    if (!auditLogs || auditLogs.length === 0) return;
    
    const headers = ['Timestamp', 'Operator', 'Action', 'Asset Vector', 'Details'];
    const rows = auditLogs.map(log => [
      log.timestamp,
      log.user_id,
      log.action,
      log.resource_type || '',
      log.details ? JSON.stringify(log.details).replace(/"/g, '""') : ''
    ]);
    
    const csvContent = headers.join(',') + '\n' + 
      rows.map(e => e.map(cell => `"${cell}"`).join(',')).join('\n');
      
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'NASO-AUDIT-LOG.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
    } catch {
      set({ error: 'Failed to acknowledge alert' });
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
      return res.data.acknowledged_count;
    } catch {
      set({ error: 'Failed to acknowledge alerts' });
    }
  },

  fetchMe: async () => {
    try {
      const res = await axios.get('/users/me');
      set({ user: res.data, isAuthenticated: true });
    } catch {
      set({ isAuthenticated: false, user: null });
    }
  },
}));

export default useNasoStore;
