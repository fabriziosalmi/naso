import React from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Fingerprint, UserPlus, Workflow } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';

const IdentityRow = ({ identity, onDetails }) => (
  <TableRow className="border-b border-white/[0.05] hover:bg-white/[0.03] transition-colors cursor-pointer" onClick={onDetails}>
    <TableCell className="pl-5">
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08]">
          <Fingerprint size={13} strokeWidth={1.5} className={identity.is_protected ? 'text-[#FFD60A]' : 'text-[#0A84FF]'} />
        </div>
        <div>
          <p className="text-[13px] font-medium text-white tracking-tight">{identity.identifier}</p>
          <p className="text-[11px] text-zinc-500 font-mono">{identity.id?.slice(0,8).toUpperCase()}</p>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <Badge variant="outline" className="text-[11px] border-white/10 text-zinc-400 capitalize">{identity.type}</Badge>
    </TableCell>
    <TableCell>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${identity.risk_score >= 80 ? 'bg-[#FF453A]' : identity.risk_score >= 50 ? 'bg-orange-400' : 'bg-[#32D74B]'}`}
            style={{ width: `${Math.min(identity.risk_score, 100)}%` }}
          />
        </div>
        <span className={`text-[12px] font-semibold w-8 text-right ${identity.risk_score >= 80 ? 'text-[#FF453A]' : identity.risk_score >= 50 ? 'text-orange-400' : 'text-[#32D74B]'}`}>
          {identity.risk_score}
        </span>
      </div>
    </TableCell>
    <TableCell className="text-right pr-5">
      <Button variant="outline" size="sm" className="h-7 text-[11px] font-medium border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 bg-transparent rounded-full px-3">
        Insights
      </Button>
    </TableCell>
  </TableRow>
);

export default function Identities({ openAddModal }) {
  const { identities, fetchIdentityInsights, isLoading, triggerIdentityMerging } = useNasoStore();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Master Identities</h1>
          <p className="text-[13px] text-zinc-500 mt-0.5">Deep forensic reconnaissance & target profiling</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={() => triggerIdentityMerging()} variant="outline" className="h-9 px-4 text-[13px] font-medium border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 bg-transparent rounded-full shadow-sm">
            <Workflow size={15} className="mr-2 text-[#0A84FF]" strokeWidth={2} /> Auto Merge
          </Button>
          <Button onClick={openAddModal} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
            <UserPlus size={15} className="mr-2" strokeWidth={2} /> Add Identity
          </Button>
        </div>
      </div>

      <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden rounded-2xl shadow-sm">
        <Table>
          <TableHeader className="bg-black/20">
            <TableRow className="border-b border-white/[0.05] h-11">
              <TableHead className="text-[12px] font-medium text-zinc-500 pl-5">Asset Identifier</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Type</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Threat Exposure</TableHead>
              <TableHead className="text-right pr-5 text-[12px] font-medium text-zinc-500">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {identities.map((id) => (
              <IdentityRow key={id.id} identity={id} onDetails={() => fetchIdentityInsights(id.id)} />
            ))}
            {isLoading ? (
                <TableRow>
                    <TableCell colSpan={4} className="h-40 text-center text-zinc-500 font-mono text-xs uppercase tracking-[0.3em]">
                       <div className="flex items-center justify-center gap-3">
                         <div className="w-2 h-2 bg-[#0A84FF] rounded-full animate-ping"></div>
                         Syncing Identities...
                       </div>
                    </TableCell>
                </TableRow>
            ) : identities.length === 0 && (
                <TableRow>
                    <TableCell colSpan={4} className="h-48">
                         <div className="flex flex-col items-center justify-center text-zinc-500 gap-4">
                            <div className="relative">
                               <div className="absolute inset-0 bg-[#0A84FF]/20 blur-xl rounded-full"></div>
                               <Fingerprint size={36} className="text-[#0A84FF] relative z-10 opacity-80" strokeWidth={1} />
                            </div>
                            <div className="text-center">
                                <p className="text-[13px] font-semibold text-white tracking-tight">No Identities Tracked</p>
                                <p className="text-[12px] text-zinc-500 mt-1">Register a target vector to begin forensic cross-correlation.</p>
                            </div>
                         </div>
                    </TableCell>
                </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
