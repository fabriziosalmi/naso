import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Radar, X, AlertTriangle, Fingerprint, Database, Calendar, Shield, Cpu, ExternalLink } from 'lucide-react';
import NetworkGraphPro from '../components/NetworkGraph';
import useNasoStore from '../store/useNasoStore';

// --- Node Inspector Component ---
const NodeInspector = ({ node, onClose }) => {
  if (!node) return null;
  const isLeak = node.type === 'leak';
  const colorRing = isLeak ? (node.risk >= 80 ? 'border-[#FF453A]/30' : 'border-[#FF9F0A]/30') : (node.isProtected ? 'border-[#FFD60A]/30' : 'border-[#0A84FF]/30');
  const Icon = isLeak ? Database : (node.isProtected ? Shield : Fingerprint);

  return (
    <div className="w-[340px] flex-shrink-0 bg-[#1C1C1E] border border-white/[0.08] rounded-2xl shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right-8 duration-300">
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

       <div className="p-4 border-t border-white/[0.05]">
          <Button variant="outline" className="w-full text-[12px] h-9 bg-black/20 hover:bg-black/40 border-white/[0.1] text-zinc-300">
             <ExternalLink size={14} className="mr-2" />
             View Full Details
          </Button>
       </div>
    </div>
  );
};

// --- Main Page ---
export default function Topology() {
  const { graphData, fetchGraphData, isLoading } = useNasoStore();
  const [selectedNode, setSelectedNode] = useState(null);

  // If graph data changes, close inspector if selected node is no longer there
  React.useEffect(() => {
    if (selectedNode && graphData?.nodes) {
       if (!graphData.nodes.find(n => n.id === selectedNode.id)) {
           setSelectedNode(null);
       }
    }
  }, [graphData]);

  return (
    <div className="h-[calc(100vh-110px)] flex flex-col gap-5">
      {/* Header */}
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Intelligence Topology</h1>
          <p className="text-[13px] text-zinc-500 mt-0.5">Interactive Relationship Map</p>
        </div>
        <Button onClick={() => fetchGraphData()} disabled={isLoading} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
          {isLoading ? <Cpu size={15} className="mr-2 animate-spin" /> : <Radar size={15} className="mr-2" strokeWidth={2} />} 
          Re-Analyze
        </Button>
      </div>

      {/* Main Content Area: Graph + Inspector */}
      <div className="flex-1 flex gap-5 min-h-0 relative">
        <div className={`transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)] ${selectedNode ? 'w-[calc(100%-360px)]' : 'w-full'}`}>
           <NetworkGraphPro 
              data={graphData} 
              isLoading={isLoading} 
              onNodeClick={setSelectedNode}
           />
        </div>

        {/* Side Panel */}
        {selectedNode && (
          <NodeInspector node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  );
}
