import { useEffect, useRef, useState } from 'react';

/**
 * Animates a number from its previous value to `target` over `duration` ms.
 * Respects prefers-reduced-motion — snaps immediately in that mode.
 */
export function useCountUp(target, { duration = 700 } = {}) {
  const [value, setValue] = useState(typeof target === 'number' ? target : 0);
  const fromRef = useRef(typeof target === 'number' ? target : 0);
  const rafRef = useRef(null);
  const startRef = useRef(null);

  useEffect(() => {
    if (typeof target !== 'number' || Number.isNaN(target)) {
      setValue(target);
      return;
    }
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      fromRef.current = target;
      setValue(target);
      return;
    }

    const from = fromRef.current;
    const to = target;
    startRef.current = null;

    const tick = (ts) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const progress = Math.min(1, elapsed / duration);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = from + (to - from) * eased;
      setValue(Math.round(next));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);

  return value;
}
