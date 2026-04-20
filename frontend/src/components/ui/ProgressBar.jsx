import React, { useEffect, useRef, useState } from 'react';
import useNasoStore from '@/store/useNasoStore';

/**
 * Top-of-page 2px progress bar (YouTube/NProgress style). Tracks the store's
 * `isLoading` flag: when a network operation begins, climbs asymptotically
 * toward 85%, then completes and fades out when loading clears.
 */
export default function ProgressBar() {
  const isLoading = useNasoStore(s => s.isLoading);
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef(null);
  const fadeTimeoutRef = useRef(null);

  useEffect(() => {
    const clearTimer = () => { if (timerRef.current) clearInterval(timerRef.current); timerRef.current = null; };
    const clearFade = () => { if (fadeTimeoutRef.current) clearTimeout(fadeTimeoutRef.current); fadeTimeoutRef.current = null; };

    if (isLoading) {
      clearFade();
      setVisible(true);
      setProgress((p) => (p > 10 ? p : 10));
      clearTimer();
      timerRef.current = setInterval(() => {
        setProgress((p) => {
          // Asymptotic climb toward 85%, never reaches it on its own.
          if (p >= 85) return p;
          const step = (85 - p) * 0.08;
          return Math.min(85, p + step);
        });
      }, 180);
    } else if (visible) {
      clearTimer();
      setProgress(100);
      fadeTimeoutRef.current = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 320);
    }

    return () => { clearTimer(); clearFade(); };
  }, [isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!visible) return null;

  return (
    <div
      className="fixed top-0 left-0 right-0 z-[130] h-[2px] pointer-events-none"
      role="progressbar"
      aria-label="Intelligence sync progress"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full bg-gradient-to-r from-[#0A84FF] via-[#5E5CE6] to-[#0A84FF] shadow-[0_0_10px_rgba(10,132,255,0.7)] transition-all duration-[180ms] ease-out"
        style={{
          width: `${progress}%`,
          opacity: progress >= 100 ? 0 : 1,
          transitionProperty: 'width, opacity',
        }}
      />
    </div>
  );
}
