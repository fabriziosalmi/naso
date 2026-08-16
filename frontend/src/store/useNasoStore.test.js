import { describe, it, expect, beforeEach, vi } from 'vitest';
import useNasoStore from './useNasoStore';
import axios from 'axios';

vi.mock('axios', () => {
    // useNasoStore registers a request interceptor at module load to attach
    // the X-Naso-CSRF header on mutating calls. The mock has to expose
    // `interceptors.request.use` or the import throws before any test runs.
    // The interceptor's behaviour is covered end to end by test_csrf.py.
    return {
        default: {
            post: vi.fn(),
            get: vi.fn(),
            defaults: { withCredentials: false },
            interceptors: { request: { use: vi.fn() } }
        }
    };
});

describe('useNasoStore', () => {
  beforeEach(() => {
    useNasoStore.setState({
        user: null,
        isAuthenticated: false,
        token: null,
        leaks: [],
        identities: [],
        auditLogs: [],
        darkWebResults: [],
        graphData: { nodes: [], links: [] },
        isLoading: false,
        error: null,
    });
    vi.clearAllMocks();
  });

  it('should initialize with default values', () => {
    const state = useNasoStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.leaks).toEqual([]);
    expect(state.isLoading).toBe(false);
  });

  it('should handle login success', async () => {
    axios.post.mockResolvedValueOnce({ status: 200, data: { status: 'success' } });

    await useNasoStore.getState().login('admin@naso.local', 'password');

    const state = useNasoStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
  });

  it('should handle fetchLeaks', async () => {
    const mockLeaks = [{ id: '1', source: 'github', severity_score: 80 }];
    useNasoStore.setState({ isAuthenticated: true });
    axios.get.mockResolvedValueOnce({ data: mockLeaks });

    await useNasoStore.getState().fetchLeaks();

    const state = useNasoStore.getState();
    expect(state.leaks).toEqual(mockLeaks);
  });

  it('should flush state securely on logout', async () => {
    useNasoStore.setState({
      token: 'some-token',
      isAuthenticated: true,
      user: { email: 'admin' },
      leaks: [1, 2, 3],
      identities: ['target_alpha'],
      auditLogs: ['action_1']
    });

    axios.post.mockResolvedValueOnce({});

    await useNasoStore.getState().logout();
    
    const state = useNasoStore.getState();
    expect(state.token).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.leaks).toEqual([]);
    expect(state.identities).toEqual([]);
    expect(state.auditLogs).toEqual([]);
  });

  it('should engage Shodan API loader toggle', async () => {
    useNasoStore.setState({ isAuthenticated: true });

    axios.get
      .mockResolvedValueOnce({ data: { success: true } })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    const shodanPromise = useNasoStore.getState().searchShodan('127.0.0.1');
    expect(useNasoStore.getState().isLoading).toBe(true);

    await shodanPromise;

    expect(axios.get).toHaveBeenCalledWith(
        '/leaks/recon/shodan',
        expect.objectContaining({ params: { ip: '127.0.0.1' } })
    );
    expect(useNasoStore.getState().isLoading).toBe(false);
  });
});
