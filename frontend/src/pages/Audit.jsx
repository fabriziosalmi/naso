import React, { useMemo, useState } from 'react';
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download, ScrollText, Search, X, ChevronRight, Copy, Check } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';
import { toast } from '../store/useToastStore';
import { SkeletonTable } from '../components/ui/Skeleton';
import { Input, Select } from '../components/ui/Input';

function AuditLogRow({ log }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const hasDetails = log.details && Object.keys(log.details).length > 0;

  const copyPayload = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(JSON.stringify(log, null, 2));
      setCopied(true);
      toast.success('Log entry copied');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Copy failed');
    }
  };

  return (
    <>
      <TableRow
        className={`border-b border-white/[0.05] transition-colors ${hasDetails ? 'hover:bg-white/[0.03] cursor-pointer' : ''}`}
        onClick={hasDetails ? () => setOpen(o => !o) : undefined}
        aria-expanded={hasDetails ? open : undefined}
      >
        <TableCell className="pl-5">
          <div className="flex items-center gap-3">
            <ChevronRight
              size={13}
              strokeWidth={2}
              className={`text-zinc-600 transition-transform ${open ? 'rotate-90' : ''} ${hasDetails ? '' : 'opacity-0'}`}
            />
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
      {open && hasDetails && (
        <TableRow className="bg-black/30 border-b border-white/[0.05]">
          <TableCell colSpan={4} className="p-0">
            <div className="px-6 py-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">Chain-of-custody payload</span>
                <button
                  onClick={copyPayload}
                  className="flex items-center gap-1.5 h-6 px-2 rounded-md text-[10px] font-medium text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  {copied ? <Check size={10} className="text-[#32D74B]" /> : <Copy size={10} strokeWidth={1.8} />}
                  {copied ? 'Copied' : 'Copy JSON'}
                </button>
              </div>
              <pre className="text-[11px] font-mono text-zinc-300 bg-black/60 border border-white/[0.05] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-72">
{JSON.stringify(log.details, null, 2)}
              </pre>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                <div>
                  <p className="text-zinc-600 uppercase tracking-wider text-[9px]">Event ID</p>
                  <p className="text-zinc-300 truncate">{log.id?.slice(0, 12) || '—'}</p>
                </div>
                <div>
                  <p className="text-zinc-600 uppercase tracking-wider text-[9px]">User</p>
                  <p className="text-zinc-300 truncate">{log.user_id?.slice(0, 12) || '—'}</p>
                </div>
                <div>
                  <p className="text-zinc-600 uppercase tracking-wider text-[9px]">Resource</p>
                  <p className="text-zinc-300 truncate">{log.resource_type || '—'}</p>
                </div>
                <div>
                  <p className="text-zinc-600 uppercase tracking-wider text-[9px]">UTC</p>
                  <p className="text-zinc-300">{new Date(log.timestamp).toISOString().slice(0, 19)}Z</p>
                </div>
              </div>
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function actionCategory(action) {
  if (!action) return 'other';
  if (action.includes('CREATE') || action.includes('ADD') || action.includes('REGISTER')) return 'create';
  if (action.includes('DELETE') || action.includes('REMOVE')) return 'delete';
  if (action.includes('RECON') || action.includes('DARK') || action.includes('PROBE')) return 'recon';
  if (action.includes('UPDATE') || action.includes('EDIT') || action.includes('MERGE')) return 'update';
  return 'other';
}

export default function Audit() {
  const { auditLogs, exportAuditCsv, isLoading } = useNasoStore();

  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [daysFilter, setDaysFilter] = useState('all');

  const filtered = useMemo(() => {
    const now = Date.now();
    const dayMs = 86_400_000;
    const dayWindow = daysFilter === 'all' ? Infinity : parseInt(daysFilter, 10) * dayMs;
    const q = query.trim().toLowerCase();

    return auditLogs.filter((log) => {
      if (daysFilter !== 'all') {
        const ts = new Date(log.timestamp).getTime();
        if (Number.isFinite(ts) && now - ts > dayWindow) return false;
      }
      if (categoryFilter !== 'all' && actionCategory(log.action) !== categoryFilter) return false;
      if (!q) return true;
      const hay = [
        log.action,
        log.user_id,
        log.resource_type,
        log.details ? JSON.stringify(log.details) : '',
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [auditLogs, query, categoryFilter, daysFilter]);

  const resetFilters = () => { setQuery(''); setCategoryFilter('all'); setDaysFilter('all'); };
  const anyFilter = query || categoryFilter !== 'all' || daysFilter !== 'all';

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Audit &amp; Compliance</h1>
          {/* Not "Immutable forensic accountability — every operation hashed
              and logged", which was wrong three times over: the chain is
              tamper-evident rather than immutable (anyone with database access
              can still change a row, they just cannot do it unnoticed),
              authentication is not audited at all, and rows written before the
              chain existed carry no hash. The security guide says all of this;
              the page a compliance officer actually reads said the opposite. */}
          <p className="text-[13px] text-zinc-500 mt-0.5">
            Tamper-evident ledger — each entry hashed against the one before it, verifiable on demand
          </p>
        </div>
        <Button onClick={exportAuditCsv} disabled={auditLogs.length === 0} variant="outline" className="h-9 px-5 text-[13px] font-medium border-white/10 bg-transparent text-zinc-300 hover:text-white hover:bg-white/10 rounded-full shrink-0">
          <Download size={14} className="mr-2" strokeWidth={1.5} /> Export CSV
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-3 md:items-center">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" strokeWidth={1.8} />
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actions, users, payload…"
            aria-label="Filter audit log"
            className="pl-9"
          />
        </div>
        <Select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Action category"
          className="md:w-48"
        >
          <option value="all">All actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
          <option value="recon">Reconnaissance</option>
          <option value="other">Other</option>
        </Select>
        <Select
          value={daysFilter}
          onChange={(e) => setDaysFilter(e.target.value)}
          aria-label="Time range"
          className="md:w-40"
        >
          <option value="all">All time</option>
          <option value="1">Last 24h</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
        </Select>
        {anyFilter && (
          <Button variant="ghost" onClick={resetFilters} className="h-10 rounded-xl text-[12px] text-zinc-400 hover:text-white">
            <X size={13} className="mr-1.5" /> Reset
          </Button>
        )}
      </div>

      {/* Count readout */}
      <div className="flex items-center justify-between text-[11px] text-zinc-500 font-mono uppercase tracking-wider">
        <span>
          {filtered.length.toLocaleString()} {filtered.length === 1 ? 'event' : 'events'}
          {anyFilter && <span className="text-zinc-600"> · of {auditLogs.length.toLocaleString()} total</span>}
        </span>
      </div>

      <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] overflow-hidden rounded-2xl shadow-sm">
        <Table>
          <TableHeader className="bg-black/20">
            <TableRow className="border-b border-white/[0.05] h-11">
              <TableHead className="text-[12px] font-medium text-zinc-500 pl-5">Operator &amp; Action</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Asset Vector</TableHead>
              <TableHead className="text-[12px] font-medium text-zinc-500">Details</TableHead>
              <TableHead className="text-right pr-5 text-[12px] font-medium text-zinc-500">Timestamp (UTC)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && auditLogs.length === 0 ? (
              <SkeletonTable rows={6} columns={4} widths={['w-48', 'w-20', 'w-56', 'w-28']} />
            ) : filtered.map((log) => (
              <AuditLogRow key={log.id} log={log} />
            ))}
            {!isLoading && auditLogs.length === 0 && (
                <TableRow>
                    <TableCell colSpan={4} className="h-48">
                         <div className="flex flex-col items-center justify-center text-zinc-500 gap-4">
                            <div className="relative">
                               <div className="absolute inset-0 bg-[#0A84FF]/20 blur-xl rounded-full"></div>
                               <ScrollText size={36} className="text-[#0A84FF] relative z-10 opacity-80" strokeWidth={1} />
                            </div>
                            <div className="text-center">
                                <p className="text-[13px] font-semibold text-white tracking-tight">No Audit Operations Logged</p>
                                <p className="text-[12px] text-zinc-500 mt-1">Actions performed by forensic operators will be cryptographically hashed here.</p>
                            </div>
                         </div>
                    </TableCell>
                </TableRow>
            )}
            {!isLoading && auditLogs.length > 0 && filtered.length === 0 && (
                <TableRow>
                    <TableCell colSpan={4} className="h-32">
                         <div className="flex flex-col items-center justify-center text-zinc-500 gap-2">
                            <Search size={20} className="text-zinc-700" strokeWidth={1.2} />
                            <p className="text-[13px] font-medium text-zinc-400">No events match your filters</p>
                            <button onClick={resetFilters} className="text-[12px] text-[#0A84FF] hover:text-[#007AFF] transition-colors">Reset filters</button>
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
