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
      console.error("Audit log fetch failed");
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
      console.error("Graph fetch failed");
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
      console.error("Screenshot fetch failed");
      return null;
    }
  },

  clearSelectedIdentity: () => set({ selectedIdentityInsights: null }),
  clearError: () => set({ error: null })
}));

export default useNasoStore;
