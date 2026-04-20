import React, { useState, useEffect } from 'react';
import Joyride, { STATUS, EVENTS } from 'react-joyride';

// Bump when we meaningfully change the tour — users who already finished the
// old one will see the refresher on first load.
const TOUR_VERSION = '2';
const STORAGE_KEY = 'naso_tour_version';

const STEPS = [
  {
    target: 'body',
    placement: 'center',
    disableBeacon: true,
    title: 'Welcome, Operator',
    content:
      'NASO is your forensic intelligence cockpit — Tor reconnaissance, breach correlation, and a local AI co-analyst under one audit-grade ledger. Quick tour?',
  },
  {
    target: '[data-tour="navigation"]',
    placement: 'right',
    title: 'Command surfaces',
    content: 'Six routes: Dashboard, Neural Topology, Master Identities, Dark Recon Probe, Audit Logs, AI Co-Analyst. Hover any item for a tooltip.',
  },
  {
    target: '[data-tour="command-palette"]',
    placement: 'bottom',
    title: 'Command palette — ⌘K / Ctrl+K',
    content:
      'Your fastest surface. Jump to any route, search identities + leaks + audit events by keyword, or fire quick actions (auto-merge, export dossier, acknowledge all).',
  },
  {
    target: '[data-tour="insights"]',
    placement: 'bottom',
    title: 'Live insights',
    content:
      'Real-time chips surface anomalies automatically: hot streaks of critical leaks, source surges, stale acknowledgements, silent perimeters. Click an action chip to triage on the spot.',
  },
  {
    target: '[data-tour="stat-cards"]',
    placement: 'top',
    title: 'Sparklines with real math',
    content:
      'Each KPI shows a 7-day rolling trend computed from actual leak timestamps. Trend arrows use the last bucket vs the prior-week average — no fake percentages.',
  },
  {
    target: '[data-tour="alerts-trigger"]',
    placement: 'bottom',
    title: 'Grouped alerts · press N',
    content:
      'Critical breaches land here grouped by time bucket (last hour, today, yesterday, this week). The bell pulses when a new critical arrives, even in an inactive tab.',
  },
  {
    target: '[data-tour="topology"]',
    placement: 'right',
    title: 'Neural Topology',
    content:
      'The correlation graph with filter chips, node search, zoom controls, floating inspector with Copy/Export JSON, and a live minimap. Critical leak arrivals pulse the graph frame.',
  },
  {
    target: '[data-tour="ai-analyst"]',
    placement: 'right',
    title: 'Local LLM Co-Analyst',
    content:
      'Private AI that executes real NASO tools — search identities, probe the dark web, flag critical. Starters are contextual: if there are unacknowledged criticals, triage is the first suggestion.',
  },
  {
    target: '[data-tour="user-menu"]',
    placement: 'top',
    title: 'Operator menu · press ?',
    content:
      'Profile, keyboard shortcuts ( ? ), help, sign out. G-prefix shortcuts: g d → Dashboard, g t → Topology, g i → Identities, g r → Dark Recon, g a → Audit.',
  },
];

export default function OnboardingTour() {
  const [run, setRun] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const current = localStorage.getItem(STORAGE_KEY);
    if (current !== TOUR_VERSION) {
      // Delay to let the shell mount so targets resolve on first open.
      const t = setTimeout(() => { setStepIndex(0); setRun(true); }, 1500);
      return () => clearTimeout(t);
    }
  }, []);

  // Let any "Restart tour" trigger (user menu, keyboard shortcut) reopen it.
  useEffect(() => {
    const restart = () => { setStepIndex(0); setRun(true); };
    window.addEventListener('naso:restart-tour', restart);
    return () => window.removeEventListener('naso:restart-tour', restart);
  }, []);

  const handleJoyrideCallback = (data) => {
    const { status, type, index, action } = data;
    const finishedStatuses = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      localStorage.setItem(STORAGE_KEY, TOUR_VERSION);
      setRun(false);
      setStepIndex(0);
      return;
    }

    // Advance/rewind stepIndex so Joyride's `continuous` mode honours manual
    // target changes (e.g. if a step target disappears, skip forward).
    if (type === EVENTS.STEP_AFTER || type === EVENTS.TARGET_NOT_FOUND) {
      setStepIndex(index + (action === 'prev' ? -1 : 1));
    }
  };

  return (
    <Joyride
      steps={STEPS}
      run={run}
      stepIndex={stepIndex}
      continuous
      showProgress
      showSkipButton
      scrollToFirstStep
      disableOverlayClose
      callback={handleJoyrideCallback}
      locale={{ back: 'Back', close: 'Close', last: 'Finish', next: 'Next', skip: 'Skip' }}
      styles={{
        options: {
          arrowColor: '#1C1C1E',
          backgroundColor: '#1C1C1E',
          overlayColor: 'rgba(0, 0, 0, 0.72)',
          primaryColor: '#0A84FF',
          textColor: '#e4e4e7',
          zIndex: 1000,
          width: 360,
        },
        tooltip: {
          borderRadius: 16,
          padding: 20,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.48)',
        },
        tooltipTitle: {
          fontSize: 15,
          fontWeight: 600,
          letterSpacing: '-0.01em',
          marginBottom: 6,
        },
        tooltipContent: {
          fontSize: 13,
          lineHeight: 1.55,
          color: '#a1a1aa',
          padding: 0,
        },
        tooltipFooter: {
          marginTop: 12,
        },
        buttonNext: {
          backgroundColor: '#0A84FF',
          borderRadius: 999,
          color: '#ffffff',
          fontSize: 12,
          fontWeight: 600,
          padding: '8px 18px',
          boxShadow: '0 4px 12px rgba(10,132,255,0.35)',
        },
        buttonBack: {
          color: '#a1a1aa',
          fontSize: 12,
          marginRight: 8,
        },
        buttonSkip: {
          color: '#71717a',
          fontSize: 12,
        },
        spotlight: {
          borderRadius: 12,
          boxShadow: '0 0 0 4px rgba(10,132,255,0.25)',
        },
      }}
    />
  );
}
