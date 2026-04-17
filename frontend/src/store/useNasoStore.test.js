import { describe, it, expect, beforeEach, vi } from 'vitest';
import useNasoStore from './useNasoStore';
import axios from 'axios';

vi.mock('axios');

describe('useNasoStore', () => {
  beforeEach(() => {
    useNasoStore.getState().logout();
    vi.clearAllMocks();
  });

  it('should initialize with default values', () => {
    const state = useNasoStore.getState();
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(state.leaks).toEqual([]);
    expect(state.isLoading).toBe(false);
  });

  it('should handle login success', async () => {
    const mockToken = 'test-token';
    axios.post.mockResolvedValueOnce({ data: { access_token: mockToken } });

    await useNasoStore.getState().login('admin@naso.local', 'password');

    const state = useNasoStore.getState();
    expect(state.token).toBe(mockToken);
    expect(state.isLoading).toBe(false);
  });

  it('should handle fetchLeaks', async () => {
    const mockLeaks = [{ id: '1', source: 'github', severity_score: 80 }];
    useNasoStore.setState({ token: 'valid-token' });
    axios.get.mockResolvedValueOnce({ data: mockLeaks });

    await useNasoStore.getState().fetchLeaks();

    const state = useNasoStore.getState();
    expect(state.leaks).toEqual(mockLeaks);
  });

  it('should flush state securely on logout', () => {
    useNasoStore.setState({
      token: 'hacked-token',
      user: { email: 'admin' },
      leaks: [1, 2, 3],
      identities: ['target_alpha'],
      auditLogs: ['action_1']
    });

    useNasoStore.getState().logout();
    
    const state = useNasoStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(state.leaks).toEqual([]);
    expect(state.identities).toEqual([]);
    expect(state.auditLogs).toEqual([]);
  });

  it('should engage Shodan API loader toggle', async () => {
    useNasoStore.setState({ token: 'valid-token' });
    
    // Simulate slow network request
    let resolveAxios;
    axios.get.mockReturnValueOnce(new Promise(resolve => {
        resolveAxios = resolve;
    }));

    const shodanPromise = useNasoStore.getState().searchShodan('127.0.0.1');
    expect(useNasoStore.getState().isLoading).toBe(true);

    resolveAxios({ data: { success: true } });
    await shodanPromise;

    expect(axios.get).toHaveBeenCalledWith(
        '/leaks/recon/shodan', 
        expect.objectContaining({ params: { ip: '127.0.0.1' } })
    );
  });
});
