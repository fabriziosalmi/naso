import { useEffect } from 'react';

/**
 * Keeps the browser tab title and favicon in sync with unacknowledged count —
 * so analysts see new criticals even when NASO is backgrounded.
 * The favicon dot is drawn onto a canvas over the base logo at runtime.
 */
export default function useTabAwareness({ unacknowledged, online, baseTitle = 'NASO · Forensic OS' }) {
  useEffect(() => {
    const prefix = unacknowledged > 0 ? `(${unacknowledged > 9 ? '9+' : unacknowledged}) ` : '';
    const status = online ? '' : ' · offline';
    document.title = `${prefix}${baseTitle}${status}`;
  }, [unacknowledged, online, baseTitle]);

  useEffect(() => {
    // Paint a dot onto a canvas favicon. Falls back silently if the base logo fails.
    const link = document.querySelector("link[rel~='icon']") || (() => {
      const el = document.createElement('link');
      el.rel = 'icon';
      el.type = 'image/png';
      document.head.appendChild(el);
      return el;
    })();

    const base = new Image();
    base.crossOrigin = 'anonymous';
    base.src = '/naso-logo.svg';

    const paint = () => {
      try {
        const size = 64;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, size, size);
        try { ctx.drawImage(base, 0, 0, size, size); } catch { /* noop — svg may fail CORS */ }

        if (unacknowledged > 0) {
          const r = 14;
          ctx.beginPath();
          ctx.arc(size - r - 2, r + 2, r, 0, Math.PI * 2);
          ctx.fillStyle = '#FF453A';
          ctx.fill();
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 20px -apple-system, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(unacknowledged > 9 ? '9+' : String(unacknowledged), size - r - 2, r + 3);
        }

        link.href = canvas.toDataURL('image/png');
      } catch {
        /* ignore — favicon is cosmetic */
      }
    };

    if (base.complete) paint();
    else base.onload = paint;
  }, [unacknowledged]);
}
