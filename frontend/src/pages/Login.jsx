import React, { useState } from 'react';
import { Shield, Loader2, AlertCircle } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';

export default function Login() {
  const { login, isLoading, error, clearError } = useNasoStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    await login(email, password);
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-6 relative overflow-hidden">
      {/* Background ambient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#0A84FF]/[0.04] rounded-full blur-[120px]" />
      </div>

      <div className="w-full max-w-sm relative z-10">
        {/* Logo & Title */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-16 h-16 bg-white/[0.03] rounded-[20px] border border-white/[0.08] flex items-center justify-center mb-6 shadow-2xl relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[#0A84FF]/20 to-transparent opacity-50" />
            <Shield size={30} className="text-[#0A84FF] relative z-10" strokeWidth={1.5} />
          </div>
          <h1 className="text-[28px] font-bold tracking-tight text-white">NASO</h1>
          <p className="text-[14px] text-zinc-500 mt-1">Forensic Intelligence Platform</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[12px] font-medium text-zinc-400 block mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => { setEmail(e.target.value); if (error) clearError(); }}
              placeholder="operator@naso.local"
              autoFocus
              className="w-full bg-[#111111] border border-white/[0.08] rounded-xl px-4 py-3 text-[14px] text-white placeholder:text-zinc-600 focus:border-[#0A84FF]/50 focus:outline-none focus:ring-1 focus:ring-[#0A84FF]/20 transition-all"
            />
          </div>
          <div>
            <label className="text-[12px] font-medium text-zinc-400 block mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => { setPassword(e.target.value); if (error) clearError(); }}
              placeholder="Enter credentials"
              className="w-full bg-[#111111] border border-white/[0.08] rounded-xl px-4 py-3 text-[14px] text-white placeholder:text-zinc-600 focus:border-[#0A84FF]/50 focus:outline-none focus:ring-1 focus:ring-[#0A84FF]/20 transition-all"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[#FF453A]/10 border border-[#FF453A]/20">
              <AlertCircle size={14} className="text-[#FF453A] shrink-0" strokeWidth={2} />
              <span className="text-[12px] font-medium text-[#FF453A]">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || !email || !password}
            className="w-full h-11 bg-[#0A84FF] hover:bg-[#007AFF] disabled:bg-[#0A84FF]/50 disabled:cursor-not-allowed text-white text-[14px] font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 mt-2"
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              'Authenticate'
            )}
          </button>
        </form>

        <p className="text-center text-[11px] text-zinc-600 mt-8">
          Secured by signed JWT. All sessions are audited.
        </p>
      </div>
    </div>
  );
}
