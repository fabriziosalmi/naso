import React from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download, ScrollText } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';

const AuditLogRow = ({ log }) => (
  <TableRow className="border-b border-white/[0.05] hover:bg-white/[0.03] transition-colors">
    <TableCell className="pl-5">
      <div className="flex items-center gap-3">
        <div className={`p-1.5 rounded-lg ${
          log.action?.includes('CREATE') ? 'bg-[#32D74B]/10' :
          log.action?.includes('DELETE') ? 'bg-[#FF453A]/10' :
          log.action?.includes('RECON') || log.action?.includes('DARK') ? 'bg-purple-500/10' :
          'bg-[#0A84FF]/10'
        }`}>
          <ScrollText size={13} strokeWidth={1.5} className={`${
            log.action?.includes('CREATE') ? 'text-[#32D74B]' :
            log.action?.includes('DELETE') ? 'text-[#FF453A]' :
            log.action?.includes('RECON') || log.action?.includes('DARK') ? 'text-purple-400' :
            'text-[#0A84FF]'
          }`} />
        </div>
        <div>
          <p className="text-[13px] font-medium text-white">{log.action?.replace(/_/g, ' ')}</p>
          <p className="text-[11px] text-zinc-500">User: {log.user_id?.slice(0,8)}</p>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <Badge variant="outline" className="text-[11px] border-white/10 text-zinc-400 capitalize">{log.resource_type || '—'}</Badge>
    </TableCell>
    <TableCell>
      <p className="text-[12px] text-zinc-400 font-mono truncate max-w-[200px]">
        {log.details ? JSON.stringify(log.details).slice(0, 60) : '—'}
      </p>
    </TableCell>
    <TableCell className="text-right pr-5">
      <span className="text-[11px] text-zinc-500 font-mono">
        {new Date(log.timestamp).toLocaleString()}
      </span>
    </TableCell>
  </TableRow>
);

export default function Audit() {
  const { auditLogs, exportAuditCsv, isLoading } = useNasoStore();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Audit & Compliance</h1>
          <p className="text-[13px] text-zinc-500 mt-0.5">Immutable forensic accountability — every operation hashed and logged</p>
        </div>
        <Button onClick={exportAuditCsv} disabled={auditLogs.length === 0} variant="outline" className="h-9 px-5 text-[13px] font-medium border-white/10 bg-transparent text-zinc-300 hover:text-white hover:bg-white/10 rounded-full">
          <Download size={14} className="mr-2" strokeWidth={1.5} /> Export CSV
        </Button>
      </div>

      <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden rounded-2xl shadow-sm">
        <Table>
          <TableHeader className="bg-black/20">
            <TableRow className="border-b border-white/[0.05] h-11">
              <TableHead className="text-[12px] font-medium text-zinc-500 pl-5">Operator & Action</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Asset Vector</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Details</TableHead>
              <TableHead className="text-right pr-5 text-[12px] font-medium text-zinc-500">Timestamp (UTC)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {auditLogs.map((log) => (
              <AuditLogRow key={log.id} log={log} />
            ))}
            {isLoading ? (
                <TableRow>
                    <TableCell colSpan={4} className="h-40 text-center text-zinc-500 font-mono text-xs uppercase tracking-[0.3em]">
                       <div className="flex items-center justify-center gap-3">
                         <div className="w-2 h-2 bg-[#0A84FF] rounded-full animate-ping"></div>
                         Syncing Chain of Custody...
                       </div>
                    </TableCell>
                </TableRow>
            ) : auditLogs.length === 0 && (
                <TableRow>
                    <TableCell colSpan={4} className="h-40 text-center text-zinc-600 text-[13px]">
                        No audit entries logged yet.
                    </TableCell>
                </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
