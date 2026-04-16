import { create } from 'zustand';
import axios from 'axios';

const useNasoStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem('naso_token') || null,
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
      const { token } = get();
      const res = await axios.get('/ai/health', {
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ aiStatus: res.data.status });
      return res.data;
    } catch {
      set({ aiStatus: 'offline' });
      return { status: 'offline' };
    }
  },

  // Stream a message to the AI Co-Analyst
  sendAiMessage: async (content) => {
    const { token, chatHistory, activeInvestigationId } = get();
    if (!token || !content.trim()) return;

    const userMsg = { id: Date.now().toString(), role: 'user', content };
    const history = [...chatHistory, userMsg];
    set({ chatHistory: history, isAiStreaming: true, error: null });

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg = { id: assistantMsgId, role: 'assistant', content: '', toolCalls: [], toolResults: [] };
    set(state => ({ chatHistory: [...state.chatHistory, assistantMsg] }));

    try {
      const response = await fetch('/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          messages: history.map(m => ({ role: m.role, content: m.content })),
          investigation_id: activeInvestigationId,
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

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
    } catch (err) {
      set(state => {
        const msgs = [...state.chatHistory];
        const idx = msgs.findIndex(m => m.id === assistantMsgId);
        if (idx !== -1) msgs[idx] = { ...msgs[idx], content: `⚠️ Connection error: ${err.message}`, isError: true };
        return { chatHistory: msgs };
      });
    } finally {
      set({ isAiStreaming: false });
    }
  },

  clearChatHistory: () => set({ chatHistory: [], evidencePanel: [] }),

  // Investigation Plans
  fetchInvestigations: async () => {
    const { token } = get();
    if (!token) return;
    try {
      const res = await axios.get('/ai/plans', { headers: { Authorization: `Bearer ${token}` } });
      set({ investigations: res.data });
    } catch { /* silent */ }
  },

  createInvestigation: async (title, description) => {
    const { token } = get();
    if (!token) return;
    try {
      const res = await axios.post('/ai/plans', { title, description }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      set(state => ({ investigations: [res.data, ...state.investigations], activeInvestigationId: res.data.id }));
      return res.data;
    } catch (err) {
      set({ error: 'Failed to create investigation plan' });
    }
  },

  updateInvestigation: async (planId, updates) => {
    const { token } = get();
    if (!token) return;
    try {
      await axios.patch(`/ai/plans/${planId}`, updates, { headers: { Authorization: `Bearer ${token}` } });
      get().fetchInvestigations();
    } catch { /* silent */ }
  },

  deleteInvestigation: async (planId) => {
    const { token } = get();
    if (!token) return;
    try {
      await axios.delete(`/ai/plans/${planId}`, { headers: { Authorization: `Bearer ${token}` } });
      set(state => ({
        investigations: state.investigations.filter(p => p.id !== planId),
        activeInvestigationId: state.activeInvestigationId === planId ? null : state.activeInvestigationId,
      }));
    } catch { /* silent */ }
  },

  addTaskToInvestigation: async (planId, content) => {
    const { token } = get();
    if (!token) return;
    try {
      await axios.post(`/ai/plans/${planId}/tasks`, { content }, { headers: { Authorization: `Bearer ${token}` } });
      get().fetchInvestigations();
    } catch { /* silent */ }
  },

  updateTask: async (planId, taskId, updates) => {
    const { token } = get();
    if (!token) return;
    try {
      await axios.patch(`/ai/plans/${planId}/tasks/${taskId}`, updates, { headers: { Authorization: `Bearer ${token}` } });
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
      
      const response = await axios.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const { access_token } = response.data;
      localStorage.setItem('naso_token', access_token);
      set({ token: access_token, isLoading: false });
    } catch (err) {
      set({ error: 'Autenticazione fallita', isLoading: false });
    }
  },

  logout: () => {
    localStorage.removeItem('naso_token');
    set({ user: null, token: null, leaks: [], identities: [], auditLogs: [], darkWebResults: [] });
  },

  // Leaks Actions
  fetchLeaks: async () => {
    const { token } = get();
    if (!token) return;
    
    set({ isLoading: true });
    try {
      const response = await axios.get('/leaks/', {
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ leaks: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Errore nel recupero dei leak', isLoading: false });
    }
  },

  // Identity Actions (Q)
  addIdentity: async (identifier, type) => {
    const { token } = get();
    if (!token) return set({ error: 'Auth token missing' });
    set({ isLoading: true });
    try {
      await axios.post('/identities/', { identifier, type }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      get().fetchIdentities();
      get().fetchAuditLogs();
      set({ isLoading: false });
    } catch (err) {
      set({ error: 'Errore aggiunta identità', isLoading: false });
    }
  },
  
  fetchIdentities: async (params = {}) => {
    const { token } = get();
    if (!token) return;
    set({ isLoading: true });
    try {
      const response = await axios.get('/identities/', { 
        params,
        headers: { Authorization: `Bearer ${token}` } 
      });
      set({ identities: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Errore nel caricamento delle identità', isLoading: false });
    }
  },

  fetchIdentityInsights: async (identityId) => {
    const { token } = get();
    if (!token) return;
    set({ isLoading: true });
    try {
      const response = await axios.get(`/identities/${identityId}/insights`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ selectedIdentityInsights: response.data, isLoading: false });
    } catch (err) {
      set({ error: 'Errore nel caricamento dei dettagli identità', isLoading: false });
    }
  },

  toggleIdentityProtection: async (identityId, isProtected) => {
    const { token } = get();
    if (!token) return;
    try {
      await axios.patch(`/identities/${identityId}/protect`, 
        { is_protected: isProtected },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      get().fetchIdentities();
      get().fetchAuditLogs();
      if (get().selectedIdentityInsights?.identity.id === identityId) {
        get().fetchIdentityInsights(identityId);
      }
    } catch (err) {
      set({ error: 'Errore nella protezione identità' });
    }
  },

  // Dark Web Search (AA)
  searchDarkWeb: async (query) => {
    const { token } = get();
    if (!token) return set({ error: 'Authentication required' });
    if (!query || !query.trim()) return set({ error: 'Enter a search query before launching probe' });
    set({ isLoading: true, error: null });
    try {
      const response = await axios.get('/leaks/recon/darkweb', {
        params: { q: query.trim() },
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ darkWebResults: response.data, isLoading: false });
      get().fetchAuditLogs();
    } catch (err) {
      set({ error: 'Dark Web probe failed — check backend connectivity', isLoading: false });
    }
  },

  // Massive Export (BB)
  exportMassiveDossier: async () => {
    const { token } = get();
    if (!token) return;
    try {
      const response = await axios.get('/leaks/export/dossier', {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'NASO-FULL-DOSSIER.pdf');
      document.body.appendChild(link);
      link.click();
      get().fetchAuditLogs();
    } catch (err) {
      set({ error: 'Esportazione dossier fallita' });
    }
  },

  // System & Compliance Actions (#10)
  updateProfile: async (email) => {
    const { token } = get();
    if (!token) return set({ error: 'Auth token missing' });
    set({ isLoading: true });
    try {
      await axios.put('/users/me', { email }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      get().fetchAuditLogs();
      set({ isLoading: false });
    } catch (err) {
      set({ error: 'Errore aggiornamento profilo', isLoading: false });
    }
  },

  fetchAuditLogs: async () => {
    const { token } = get();
    if (!token) return;
    try {
      const response = await axios.get('/system/audit', {
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ auditLogs: response.data });
    } catch (err) {
      set({ error: "Audit log fetch failed" });
      console.error("Audit log fetch failed", err);
    }
  },

  fetchGraphData: async () => {
    const { token } = get();
    if (!token) return;
    try {
      const response = await axios.get('/identities/graph', {
        headers: { Authorization: `Bearer ${token}` }
      });
      set({ graphData: response.data });
    } catch (err) {
      set({ error: "Graph fetch failed" });
      console.error("Graph fetch failed", err);
    }
  },

  fetchScreenshot: async (leakId) => {
    const { token } = get();
    if (!token) return null;
    try {
      const response = await axios.get(`/leaks/${leakId}/screenshot`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      return URL.createObjectURL(response.data);
    } catch (err) {
      set({ error: "Screenshot fetch failed" });
      console.error("Screenshot fetch failed", err);
      return null;
    }
  },

  clearSelectedIdentity: () => set({ selectedIdentityInsights: null }),
  clearError: () => set({ error: null })
}));

export default useNasoStore;
