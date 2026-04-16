import React, { useEffect, useState, useRef, useMemo } from 'react';
import { Terminal as TerminalIcon, Settings } from 'lucide-react';
import { Button } from "@/components/ui/button";

export const TerminalLog = ({ logs }) => {
  const scrollRef = useRef();
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 font-mono text-xs h-48 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
        <div className="flex items-center gap-2">
            <TerminalIcon size={14} className="text-zinc-500" />
            <span className="font-semibold text-zinc-400">System Logs</span>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-1.5 scrollbar-hide text-[11px]">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-3 text-zinc-400 hover:text-zinc-300 transition-colors">
            <span className="text-zinc-600">[{log.time}]</span>
            <span className={log.type === 'error' ? 'text-red-400' : log.type === 'warn' ? 'text-amber-400' : 'text-zinc-300'}>
                {log.msg}
            </span>
          </div>
        ))}
        {logs.length === 0 && <div className="text-zinc-600">Awaiting telemetry...</div>}
      </div>
    </div>
  );
};
