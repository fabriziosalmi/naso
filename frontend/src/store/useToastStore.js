import { create } from 'zustand';

let idSeq = 0;
const nextId = () => `t_${Date.now().toString(36)}_${++idSeq}`;

const DEFAULT_DURATION = 3500;

const useToastStore = create((set, get) => ({
  toasts: [],

  push: (toast) => {
    const id = toast.id ?? nextId();
    const duration = toast.duration ?? DEFAULT_DURATION;
    const entry = {
      id,
      variant: toast.variant ?? 'info',
      title: toast.title,
      description: toast.description,
      action: toast.action,
    };
    set((s) => ({ toasts: [...s.toasts.filter(t => t.id !== id), entry] }));
    if (duration > 0) {
      setTimeout(() => get().dismiss(id), duration);
    }
    return id;
  },

  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter(t => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

// Convenience helpers — call as `toast.success('...')` anywhere in the app.
export const toast = {
  success: (title, description, opts) =>
    useToastStore.getState().push({ variant: 'success', title, description, ...opts }),
  error: (title, description, opts) =>
    useToastStore.getState().push({ variant: 'error', title, description, ...opts }),
  info: (title, description, opts) =>
    useToastStore.getState().push({ variant: 'info', title, description, ...opts }),
  warning: (title, description, opts) =>
    useToastStore.getState().push({ variant: 'warning', title, description, ...opts }),
};

export default useToastStore;
