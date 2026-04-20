import * as React from 'react';
import { cn } from '@/lib/utils';

const base =
  'w-full bg-black/40 border border-white/[0.08] rounded-xl px-4 py-2.5 text-[14px] text-white placeholder:text-zinc-500 focus:border-[#0A84FF]/60 focus:ring-2 focus:ring-[#0A84FF]/25 focus:outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

export const Input = React.forwardRef(function Input({ className, type = 'text', ...props }, ref) {
  return <input ref={ref} type={type} className={cn(base, className)} {...props} />;
});

export const Select = React.forwardRef(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(base, 'appearance-none pr-10 bg-[url("data:image/svg+xml;utf8,<svg fill=\'%2371717a\' height=\'12\' viewBox=\'0 0 24 24\' xmlns=\'http://www.w3.org/2000/svg\'><path d=\'M7 10l5 5 5-5z\'/></svg>")] bg-no-repeat bg-right-3 bg-[length:16px]', className)} {...props}>
      {children}
    </select>
  );
});

export function Label({ className, children, ...props }) {
  return (
    <label className={cn('text-[12px] font-medium text-zinc-400 block mb-2', className)} {...props}>
      {children}
    </label>
  );
}

export function Field({ label, children, hint, error }) {
  return (
    <div className="space-y-2">
      {label && <Label>{label}</Label>}
      {children}
      {hint && !error && <p className="text-[11px] text-zinc-500">{hint}</p>}
      {error && <p className="text-[11px] text-[#FF453A]">{error}</p>}
    </div>
  );
}
