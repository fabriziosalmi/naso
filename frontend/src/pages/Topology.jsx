import React, { useMemo, useRef, useState } from 'react';
import { Button } from "@/components/ui/button";
import { Radar, X, AlertTriangle, Fingerprint, Database, Calendar, Shield, Cpu, ExternalLink, Download, Copy, Check, ZoomIn, ZoomOut, Maximize2, Search } from 'lucide-react';
import NetworkGraphPro from '../components/NetworkGraph';
import GraphMinimap from '../components/ui/GraphMinimap';
import useNasoStore from '../store/useNasoStore';
import { toast } from '../store/useToastStore';
import { Input } from '../components/ui/Input';

// --- Node Inspector Component ---
const NodeInspector = ({ node, onClose }) => {
  const [copied, setCopied] = useState(false);

  if (!node) return null;
  const isLeak = node.type === 'leak';
  const colorRing = isLeak ? (node.risk >= 80 ? 'border-[#FF453A]/30' : 'border-[#FF9F0A]/30') : (node.isProtected ? 'border-[#FFD60A]/30' : 'border-[#0A84FF]/30');
  const Icon = isLeak ? Database : (node.isProtected ? Shield : Fingerprint);

  // Serializable snapshot — strip circular refs (ForceGraph mutates nodes with x/y/vx/vy + neighbors back-refs).
  const serializable = () => ({
    id: node.id,
    type: node.type,
    label: node.label,
    risk: node.risk ?? null,
    degree: node.degree ?? 0,
    isProtected: !!node.isProtected,
    source: node.source ?? null,
    neighbors: (node.neighbors ?? []).map(n => ({ id: n.id, label: n.label, type: n.type })),
    exported_at: new Date().toISOString(),
  });

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(serializable(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `node-${String(node.id).slice(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast.success('Node exported', `node-${String(node.id).slice(0, 8)}.json`);
  };

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(serializable(), null, 2));
      setCopied(true);
      toast.success('Node JSON copied to clipboard');
      setTimeout(() => setCopied(false), 1600);
    } catch {
      toast.error('Copy failed');
    }
  };

  return (
    <div className="absolute top-4 right-4 bottom-4 w-[340px] max-w-[calc(100%-2rem)] z-20 bg-[#1C1C1E]/95 backdrop-blur-2xl border border-white/[0.10] rounded-2xl shadow-[0_24px_60px_-12px_rgba(0,0,0,0.6)] overflow-hidden flex flex-col animate-in slide-in-from-right-8 duration-300">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/[0.05] flex items-start justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-white/[0.02] to-transparent pointer-events-none" />
        <div className="relative z-10">
          <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl border ${colorRing} bg-black/40 mb-3`}>
            <Icon size={20} className={isLeak ? (node.risk >= 80 ? 'text-[#FF453A]' : 'text-[#FF9F0A]') : (node.isProtected ? 'text-[#FFD60A]' : 'text-[#0A84FF]')} />
          </div>
          <h2 className="text-[16px] font-semibold text-white tracking-tight leading-tight">{node.label}</h2>
          <p className="text-[12px] text-zinc-500 mt-0.5 capitalize">{isLeak ? 'Intelligence Artifact' : 'Monitored Identity'} • Node Context</p>
        </div>
        <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors relative z-10 p-1">
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="p-5 flex-1 overflow-y-auto space-y-6">

        {/* Risk & Degree Panel */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-black/40 rounded-xl p-3 border border-white/[0.04]">
            <p className="text-[11px] text-zinc-500 mb-1 flex items-center gap-1.5"><AlertTriangle size={12}/> Severity / Risk</p>
            <p className={`text-[18px] font-semibold tracking-tight ${node.risk >= 80 ? 'text-[#FF453A]' : node.risk >= 50 ? 'text-[#FF9F0A]' : 'text-[#32D74B]'}`}>
              {node.risk || 0} <span className="text-[12px] font-medium text-zinc-600">/ 100</span>
            </p>
          </div>
          <div className="bg-black/40 rounded-xl p-3 border border-white/[0.04]">
            <p className="text-[11px] text-zinc-500 mb-1 flex items-center gap-1.5"><Cpu size={12}/> Degree Centrality</p>
            <p className="text-[18px] font-semibold tracking-tight text-white">{node.degree || 0}</p>
          </div>
        </div>

        {/* Details List */}
        <div className="space-y-3">
          <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">Properties</p>
          <div className="bg-white/[0.02] rounded-xl border border-white/[0.04] p-1">

            <div className="flex items-center justify-between p-2">
              <span className="text-[12px] text-zinc-400">Type</span>
              <span className="text-[12px] font-medium text-white capitalize">{node.type}</span>
            </div>
            {isLeak && (
              <div className="flex items-center justify-between p-2 border-t border-white/[0.03]">
                <span className="text-[12px] text-zinc-400">Source</span>
                <span className="text-[12px] font-medium text-white truncate max-w-[150px]">{node.source}</span>
              </div>
            )}
            <div className="flex items-center justify-between p-2 border-t border-white/[0.03]">
              <span className="text-[12px] text-zinc-400">UUID</span>
              <span className="text-[11px] font-mono text-zinc-500">{node.id.substring(0, 13)}...</span>
            </div>
             <div className="flex items-center justify-between p-2 border-t border-white/[0.03]">
              <span className="text-[12px] text-zinc-400 font-medium">Protection</span>
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${node.isProtected ? 'bg-[#FFD60A]/10 text-[#FFD60A]' : 'bg-white/[0.05] text-zinc-400'}`}>
                {node.isProtected ? 'VIP Asset' : 'Standard'}
              </span>
            </div>
          </div>
        </div>

        {/* Linked Nodes Preview */}
        {node.neighbors && node.neighbors.length > 0 && (
          <div className="space-y-3">
            <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">Connected Edges ({node.neighbors.length})</p>
            <div className="flex flex-wrap gap-2">
              {node.neighbors.slice(0, 15).map(neighbor => (
                <div key={neighbor.id} className="px-2.5 py-1.5 rounded-lg bg-black/40 border border-white/[0.04] text-[11px] text-zinc-300 truncate max-w-full">
                  {neighbor.label?.length > 25 ? neighbor.label.substring(0, 25) + '...' : neighbor.label}
                </div>
              ))}
              {node.neighbors.length > 15 && (
                <div className="px-2.5 py-1.5 rounded-lg bg-white/[0.02] border border-transparent text-[11px] text-zinc-500">
                  + {node.neighbors.length - 15} more...
                </div>
              )}
            </div>
          </div>
        )}
      </div>

       <div className="p-3 border-t border-white/[0.05] grid grid-cols-2 gap-2">
          <Button
            onClick={copyJson}
            variant="outline"
            className="text-[12px] h-9 bg-black/20 hover:bg-black/40 border-white/[0.1] text-zinc-300"
          >
            {copied ? <Check size={13} className="mr-1.5 text-[#32D74B]" /> : <Copy size={13} className="mr-1.5" />}
            {copied ? 'Copied' : 'Copy JSON'}
          </Button>
          <Button
            onClick={exportJson}
            variant="outline"
            className="text-[12px] h-9 bg-black/20 hover:bg-black/40 border-white/[0.1] text-zinc-300"
          >
            <Download size={13} className="mr-1.5" />
            Export
          </Button>
       </div>
    </div>
  );
};

const FILTERS = [
  { value: 'all',      label: 'All' },
  { value: 'identity', label: 'Identities' },
  { value: 'leak',     label: 'Leaks' },
  { value: 'vip',      label: 'VIP only' },
  { value: 'critical', label: 'Critical' },
];

// --- Main Page ---
export default function Topology() {
  const { graphData, fetchGraphData, isLoading, leaks } = useNasoStore();
  const [selectedNode, setSelectedNode] = useState(null);
  const [pulse, setPulse] = useState(false);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [searchHit, setSearchHit] = useState(null);
  const graphRef = useRef(null);

  // Filtered view of graphData. Keep links only when both endpoints survive.
  const filteredData = useMemo(() => {
    const src = graphData || { nodes: [], links: [] };
    if (filter === 'all') return src;

    const keep = new Set(
      src.nodes
        .filter((n) => {
          if (filter === 'identity') return n.type !== 'leak';
          if (filter === 'leak') return n.type === 'leak';
          if (filter === 'vip') return n.isProtected;
          if (filter === 'critical') return n.type === 'leak' && (n.risk ?? 0) >= 80;
          return true;
        })
        .map((n) => n.id)
    );
    return {
      nodes: src.nodes.filter((n) => keep.has(n.id)),
      links: src.links.filter((l) => {
        const sid = l.source?.id ?? l.source;
        const tid = l.target?.id ?? l.target;
        return keep.has(sid) && keep.has(tid);
      }),
    };
  }, [graphData, filter]);

  // Search within visible nodes by label — first hit wins.
  const searchMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return filteredData.nodes.filter((n) => n.label?.toLowerCase().includes(q)).slice(0, 6);
  }, [query, filteredData]);

  // If graph data changes, close inspector if selected node is no longer there
  React.useEffect(() => {
    if (selectedNode && graphData?.nodes) {
       if (!graphData.nodes.find(n => n.id === selectedNode.id)) {
           setSelectedNode(null);
       }
    }
  }, [graphData]);

  // Signature pulse: when a new critical leak arrives, briefly pulse the graph frame.
  const prevCriticalRef = React.useRef(null);
  React.useEffect(() => {
    const count = (leaks || []).filter(l => l.severity_score >= 80).length;
    if (prevCriticalRef.current !== null && count > prevCriticalRef.current) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 1700);
      prevCriticalRef.current = count;
      return () => clearTimeout(t);
    }
    prevCriticalRef.current = count;
  }, [leaks]);

  const jumpTo = (node) => {
    setSearchHit(node.id);
    setSelectedNode(node);
    graphRef.current?.centerOn(node);
  };

  return (
    <div className="h-[calc(100vh-110px)] flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 shrink-0">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Intelligence Topology</h1>
          <p className="text-[13px] text-zinc-500 mt-0.5">Interactive relationship map · {filteredData.nodes.length} of {graphData?.nodes?.length ?? 0} nodes</p>
        </div>
        <Button onClick={() => fetchGraphData()} disabled={isLoading} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm self-start sm:self-auto">
          {isLoading ? <Cpu size={15} className="mr-2 animate-spin" /> : <Radar size={15} className="mr-2" strokeWidth={2} />}
          Re-Analyze
        </Button>
      </div>

      {/* Toolbar: filter chips + search + zoom controls */}
      <div className="flex flex-col lg:flex-row gap-3 lg:items-center shrink-0">
        <div className="inline-flex items-center gap-1 p-1 rounded-full bg-black/40 border border-white/[0.06]" role="tablist" aria-label="Node filter">
          {FILTERS.map(f => (
            <button
              key={f.value}
              role="tab"
              aria-selected={filter === f.value}
              onClick={() => setFilter(f.value)}
              className={`h-7 px-3 rounded-full text-[11px] font-medium transition-colors ${
                filter === f.value ? 'bg-white/[0.08] text-white shadow-sm' : 'text-zinc-500 hover:text-white'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="relative flex-1 min-w-0 max-w-xl">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" strokeWidth={1.8} />
          <Input
            type="search"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSearchHit(null); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchMatches[0]) jumpTo(searchMatches[0]);
            }}
            placeholder="Jump to node by label…"
            aria-label="Search nodes"
            className="pl-9 py-2 text-[13px]"
          />
          {query && searchMatches.length > 0 && (
            <div className="absolute z-20 mt-1 w-full bg-[#1C1C1E]/95 backdrop-blur-2xl border border-white/[0.08] rounded-xl shadow-2xl overflow-hidden">
              {searchMatches.map((m) => (
                <button
                  key={m.id}
                  onClick={() => jumpTo(m)}
                  className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/[0.05] transition-colors"
                >
                  <span className="text-[12px] text-white truncate">{m.label}</span>
                  <span className="text-[10px] font-mono text-zinc-500 uppercase">{m.type}{m.risk ? ` · ${m.risk}` : ''}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="inline-flex items-center gap-1 p-1 rounded-full bg-black/40 border border-white/[0.06] shrink-0">
          <button onClick={() => graphRef.current?.zoomBy(1/1.3)} aria-label="Zoom out" className="h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors">
            <ZoomOut size={13} />
          </button>
          <button onClick={() => graphRef.current?.fit()} aria-label="Fit to view" className="h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors">
            <Maximize2 size={13} />
          </button>
          <button onClick={() => graphRef.current?.zoomBy(1.3)} aria-label="Zoom in" className="h-7 w-7 rounded-full text-zinc-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors">
            <ZoomIn size={13} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className={`flex-1 min-h-0 relative rounded-2xl ${pulse ? 'signature-pulse' : ''}`}>
        <NetworkGraphPro
          ref={graphRef}
          data={filteredData}
          isLoading={isLoading}
          onNodeClick={(n) => { setSelectedNode(n); setSearchHit(n?.id || null); }}
          highlightNodeId={searchHit}
        />
        {!isLoading && <GraphMinimap graphData={filteredData} forceGraphRef={graphRef} />}
        {selectedNode && (
          <NodeInspector node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  );
}
