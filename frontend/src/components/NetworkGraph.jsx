import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const EMPTY_GRAPH = { nodes: [], links: [] };

const NetworkGraphPro = ({ data }) => {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Measure container and update on resize
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });
    observer.observe(containerRef.current);
    const { offsetWidth, offsetHeight } = containerRef.current;
    if (offsetWidth > 0 && offsetHeight > 0) {
      setDimensions({ width: offsetWidth, height: offsetHeight });
    }
    return () => observer.disconnect();
  }, []);

  // Zoom to fit when data or dimensions change
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      setTimeout(() => fgRef.current?.zoomToFit(400, 60), 300);
    }
  }, [data, dimensions]);

  const graphData = (data?.nodes?.length > 0) ? data : EMPTY_GRAPH;

  const getNodeColor = (node) => {
    if (node.type === 'leak') {
      return node.risk >= 80 ? '#FF453A' : '#FF9F0A';
    }
    return node.isProtected ? '#FFD60A' : '#0A84FF';
  };

  const getNodeSize = (node) => node.type === 'leak' ? 6 : 4;

  const isEmpty = graphData.nodes.length === 0;

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative bg-black/60"
      style={{ minHeight: '500px' }}
    >
      {/* Legend */}
      <div className="absolute top-4 left-5 z-10 space-y-1 pointer-events-none">
        <p className="text-[13px] font-semibold text-white tracking-tight">Intelligence Topology</p>
        <p className="text-[11px] text-zinc-500">Interactive Force-Directed Graph</p>
      </div>

      {/* Color Legend */}
      <div className="absolute bottom-4 left-5 z-10 flex gap-5 pointer-events-none">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#0A84FF]"></div>
          <span className="text-[11px] font-medium text-zinc-500">Identity</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#FFD60A]"></div>
          <span className="text-[11px] font-medium text-zinc-500">VIP Asset</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#FF453A]"></div>
          <span className="text-[11px] font-medium text-zinc-500">Critical Leak</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#FF9F0A]"></div>
          <span className="text-[11px] font-medium text-zinc-500">Moderate Leak</span>
        </div>
      </div>

      {/* Node count badge */}
      {!isEmpty && (
        <div className="absolute top-4 right-5 z-10 px-3 py-1 rounded-full bg-white/[0.06] border border-white/[0.08]">
          <span className="text-[11px] font-medium text-zinc-400">
            {graphData.nodes.length} nodes · {graphData.links.length} links
          </span>
        </div>
      )}

      {/* Empty state */}
      {isEmpty ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-zinc-600">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="opacity-30">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
          </svg>
          <div className="text-center">
            <p className="text-[14px] font-medium text-zinc-500">No topology data</p>
            <p className="text-[12px] text-zinc-600 mt-1">Add identities or click Re-Scan to populate the graph</p>
          </div>
        </div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          nodeLabel="label"
          nodeColor={getNodeColor}
          nodeRelSize={1}
          nodeVal={getNodeSize}
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={0.004}
          linkColor={() => 'rgba(255,255,255,0.08)'}
          backgroundColor="rgba(0,0,0,0)"
          nodeCanvasObject={(node, ctx, globalScale) => {
            const size = getNodeSize(node);
            const color = getNodeColor(node);

            // Glow ring
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 3, 0, 2 * Math.PI, false);
            ctx.fillStyle = color.replace(')', ', 0.12)').replace('rgb', 'rgba').replace('#', 'rgba(').replace('rgba(', 'rgba(');
            ctx.fill();

            // Node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = color;
            ctx.fill();

            // Label at higher zoom
            if (globalScale > 2.5) {
              const label = node.label?.length > 20 ? node.label.slice(0, 20) + '…' : node.label;
              const fontSize = Math.min(12 / globalScale, 4);
              ctx.font = `${fontSize}px -apple-system, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
              ctx.fillText(label, node.x, node.y + size + 2);
            }
          }}
        />
      )}
    </div>
  );
};

export default NetworkGraphPro;
