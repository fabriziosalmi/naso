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
});
