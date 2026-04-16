import React, { useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NetworkGraphPro = ({ data }) => {
  const fgRef = useRef();

  // Reset zoom on data change
  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 100);
    }
  }, [data]);

  const getNodeColor = (node) => {
    if (node.type === 'leak') {
      return node.risk >= 80 ? '#ef4444' : '#f97316';
    }
    return node.isProtected ? '#eab308' : '#3b82f6';
  };

  const getNodeSize = (node) => {
    return node.type === 'leak' ? 6 : 4;
  };

  return (
    <div className="w-full h-full min-h-[600px] bg-zinc-950/50 rounded-xl overflow-hidden border border-zinc-800 relative">
      <div className="absolute top-4 left-6 z-10 space-y-1 pointer-events-none">
        <p className="text-xs font-semibold tracking-tight text-zinc-100">Intelligence Topology</p>
        <p className="text-[10px] text-zinc-500 font-medium">Interactive Force-Directed Graph</p>
      </div>
      
      <div className="absolute bottom-4 left-6 z-10 flex gap-4 pointer-events-none">
        <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500"></div>
            <span className="text-[8px] font-black uppercase text-zinc-500">Identity</span>
        </div>
        <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
            <span className="text-[8px] font-black uppercase text-zinc-500">VIP Asset</span>
        </div>
        <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-red-500"></div>
            <span className="text-[8px] font-black uppercase text-zinc-500">Critical Leak</span>
        </div>
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        nodeLabel="label"
        nodeColor={getNodeColor}
        nodeRelSize={1}
        nodeVal={getNodeSize}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        linkColor={() => 'rgba(255,255,255,0.1)'}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.label;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Inter, sans-serif`;
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

          // Draw circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, getNodeSize(node), 0, 2 * Math.PI, false);
          ctx.fillStyle = getNodeColor(node);
          ctx.fill();

          // Label
          if (globalScale > 3) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            ctx.fillText(label, node.x, node.y + getNodeSize(node) + 5);
          }
        }}
      />
    </div>
  );
};

export default NetworkGraphPro;
