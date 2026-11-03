import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import OnboardingTour from './OnboardingTour';

describe('OnboardingTour', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('opens on restart, shows progress and skip, and records the version when skipped', async () => {
    render(<OnboardingTour />);
    act(() => {
      window.dispatchEvent(new Event('naso:restart-tour'));
    });

    expect(await screen.findByText('Welcome, Operator')).toBeTruthy();
    // showProgress: the primary button carries "(current of total)".
    expect(screen.getByRole('button', { name: /Next \(1 of 9\)/ })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));

    // onEvent sees STATUS.SKIPPED and stores the tour version.
    await waitFor(() => expect(localStorage.getItem('naso_tour_version')).toBe('2'));
  });
});
