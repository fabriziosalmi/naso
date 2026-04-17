import React, { useState, useEffect } from 'react';
import Joyride, { STATUS } from 'react-joyride';

export default function OnboardingTour() {
  const [run, setRun] = useState(false);

  useEffect(() => {
    // Only run if the user hasn't completed the tour
    const hasTourRun = localStorage.getItem('naso_tour_completed');
    if (!hasTourRun) {
      // Slight delay to ensure DOM is mounted
      setTimeout(() => setRun(true), 1500);
    }
  }, []);

  const steps = [
    {
      target: 'body',
      content: 'Welcome to NASO Forensic Engine 🚀. We have detected anomalous activity. This quick tour will show you how to navigate your intelligence matrix.',
      placement: 'center',
    },
    {
      target: '[data-tour="topology"]',
      content: 'Here you track the global correlation graph. Threats and identities collide here.',
      placement: 'right',
    },
    {
      target: '[data-tour="ai-analyst"]',
      content: 'Stuck? Invoke your AI Co-Analyst. It has autonomous database access to assist your investigations.',
      placement: 'right',
    },
    {
      target: '[data-tour="alerts-trigger"]',
      content: 'Critical YARA matches and intelligence alerts appear here in real-time. Keep an eye on it.',
      placement: 'bottom',
    }
  ];

  const handleJoyrideCallback = (data) => {
    const { status } = data;
    const finishedStatuses = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      localStorage.setItem('naso_tour_completed', 'true');
      setRun(false);
    }
  };

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      scrollToFirstStep
      showSkipButton
      callback={handleJoyrideCallback}
      styles={{
        options: {
          arrowColor: '#18181b',
          backgroundColor: '#18181b',
          overlayColor: 'rgba(0, 0, 0, 0.7)',
          primaryColor: '#6366f1',
          textColor: '#e4e4e7',
          zIndex: 1000,
        },
        tooltipContainer: {
          textAlign: 'left',
          borderRadius: '12px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        },
        buttonNext: {
          backgroundColor: '#6366f1',
          borderRadius: '8px',
          color: '#ffffff',
          fontSize: '13px'
        },
        buttonBack: {
          color: '#a1a1aa',
          marginRight: 10
        },
        buttonSkip: {
          color: '#ef4444',
          fontSize: '13px'
        }
      }}
    />
  );
}
