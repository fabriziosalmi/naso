import React from 'react';
import { CheckCircle2, AlertTriangle, Info, X, ShieldAlert } from 'lucide-react';
import useToastStore from '@/store/useToastStore';

const VARIANT = {
  success: {
    icon: CheckCircle2,
    iconClass: 'text-[#32D74B]',
    ring: 'border-[#32D74B]/25',
    bg: 'bg-[#32D74B]/[0.06]',
    ariaRole: 'status',
  },
  error: {
    icon: ShieldAlert,
    iconClass: 'text-[#FF453A]',
    ring: 'border-[#FF453A]/25',
    bg: 'bg-[#FF453A]/[0.06]',
    ariaRole: 'alert',
  },
  warning: {
    icon: AlertTriangle,
    iconClass: 'text-[#FFD60A]',
    ring: 'border-[#FFD60A]/25',
    bg: 'bg-[#FFD60A]/[0.06]',
    ariaRole: 'status',
  },
  info: {
    icon: Info,
    iconClass: 'text-[#0A84FF]',
    ring: 'border-[#0A84FF]/25',
    bg: 'bg-[#0A84FF]/[0.06]',
    ariaRole: 'status',
  },
};

function ToastItem({ toast, onDismiss }) {
  const config = VARIANT[toast.variant] ?? VARIANT.info;
  const Icon = config.icon;
  return (
    <div
      role={config.ariaRole}
      aria-live={toast.variant === 'error' ? 'assertive' : 'polite'}
      className={`pointer-events-auto relative flex items-start gap-3 min-w-[320px] max-w-[420px] rounded-2xl border ${config.ring} ${config.bg} backdrop-blur-2xl bg-[#1C1C1E]/80 shadow-[0_8px_32px_rgba(0,0,0,0.45)] pl-4 pr-9 py-3 animate-toast-in`}
    >
      <div className="shrink-0 mt-0.5">
        <Icon size={16} className={config.iconClass} strokeWidth={1.8} />
      </div>
      <div className="flex-1 min-w-0">
        {toast.title && (
          <p className="text-[13px] font-semibold text-white tracking-tight">{toast.title}</p>
        )}
        {toast.description && (
          <p className={`text-[12px] text-zinc-400 leading-snug ${toast.title ? 'mt-0.5' : ''}`}>
            {toast.description}
          </p>
        )}
        {toast.action && (
          <button
            onClick={() => { toast.action.onClick?.(); onDismiss(); }}
            className="mt-2 text-[12px] font-medium text-[#0A84FF] hover:text-[#007AFF] transition-colors"
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="absolute right-2 top-2 p-1 rounded-md text-zinc-500 hover:text-white hover:bg-white/5 transition-colors"
      >
        <X size={12} strokeWidth={2} />
      </button>
    </div>
  );
}

export default function Toaster() {
  const toasts = useToastStore(s => s.toasts);
  const dismiss = useToastStore(s => s.dismiss);

  if (!toasts.length) return null;

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-6 right-6 z-[120] flex flex-col-reverse gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  );
}
