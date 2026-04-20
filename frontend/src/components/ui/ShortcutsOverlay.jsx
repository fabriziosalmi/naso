import React, { useEffect, useState } from 'react';
import { X, Command as CmdIcon } from 'lucide-react';

const SHORTCUTS = [
  { keys: ['⌘', 'K'], winKeys: ['Ctrl', 'K'], label: 'Open command palette' },
  { keys: ['G', 'D'], label: 'Go to Dashboard' },
  { keys: ['G', 'T'], label: 'Go to Topology' },
  { keys: ['G', 'I'], label: 'Go to Identities' },
  { keys: ['G', 'R'], label: 'Go to Dark Recon' },
  { keys: ['G', 'A'], label: 'Go to Audit' },
  { keys: ['N'], label: 'Open notifications' },
  { keys: ['Esc'], label: 'Close panel / dialog' },
  { keys: ['?'], label: 'Show this overlay' },
];

function Kbd({ children }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-md bg-white/[0.06] border border-white/[0.08] text-[11px] font-mono font-medium text-zinc-300 shadow-[inset_0_-1px_0_rgba(255,255,255,0.05)]">
      {children}
    </kbd>
  );
}

export default function ShortcutsOverlay() {
  const [open, setOpen] = useState(false);
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform);

  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || '').toLowerCase();
      const inField = tag === 'input' || tag === 'textarea' || e.target?.isContentEditable;
      if (e.key === '?' && !inField) {
        e.preventDefault();
        setOpen(v => !v);
        return;
      }
      if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[110] bg-black/70 backdrop-blur-md flex items-center justify-center px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md bg-[#1C1C1E]/95 border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-xl bg-[#0A84FF]/10 border border-[#0A84FF]/20">
              <CmdIcon size={14} className="text-[#0A84FF]" strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-[14px] font-semibold text-white tracking-tight">Keyboard shortcuts</p>
              <p className="text-[11px] text-zinc-500">Power-user navigation</p>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close shortcuts"
            className="p-1.5 rounded-md text-zinc-500 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        <ul className="divide-y divide-white/[0.04]">
          {SHORTCUTS.map((s, i) => {
            const keys = isMac || !s.winKeys ? s.keys : s.winKeys;
            return (
              <li key={i} className="flex items-center justify-between px-5 py-2.5">
                <span className="text-[13px] text-zinc-300">{s.label}</span>
                <span className="flex items-center gap-1">
                  {keys.map((k, j) => (
                    <React.Fragment key={j}>
                      <Kbd>{k}</Kbd>
                      {j < keys.length - 1 && <span className="text-zinc-600 text-[10px] mx-0.5">then</span>}
                    </React.Fragment>
                  ))}
                </span>
              </li>
            );
          })}
        </ul>

        <div className="px-5 py-3 bg-black/20 border-t border-white/[0.06] text-[10px] text-zinc-600 flex items-center justify-between">
          <span>Press <Kbd>?</Kbd> to toggle this overlay</span>
          <span>NASO • {new Date().getFullYear()}</span>
        </div>
      </div>
    </div>
  );
}
