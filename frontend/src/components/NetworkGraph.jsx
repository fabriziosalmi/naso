import React, { forwardRef, useRef, useEffect, useState, useMemo, useCallback, useImperativeHandle } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const EMPTY_GRAPH = { nodes: [], links: [] };

const NetworkGraphPro = forwardRef(function NetworkGraphPro({ data, isLoading, onNodeClick, highlightNodeId }, ref) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoverNode, setHoverNode] = useState(null);

  // Expose imperative zoom controls to parent toolbar. We also forward a
  // lowercase-named `current` field so the minimap can reach centerAt +
  // screen2GraphCoords without us re-wrapping each method.
  useImperativeHandle(ref, () => ({
    zoomBy: (factor) => {
      const fg = fgRef.current;
      if (!fg) return;
      const current = fg.zoom();
      fg.zoom(current * factor, 280);
    },
    fit: () => fgRef.current?.zoomToFit(420, 60),
    centerOn: (node) => {
      const fg = fgRef.current;
      if (!fg || !node || node.x === undefined) return;
      fg.centerAt(node.x, node.y, 600);
      fg.zoom(3, 600);
    },
    centerAt: (x, y, ms) => fgRef.current?.centerAt(x, y, ms),
    screen2GraphCoords: (x, y) => fgRef.current?.screen2GraphCoords?.(x, y),
    graph2ScreenCoords: (x, y) => fgRef.current?.graph2ScreenCoords?.(x, y),
  }), []);

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
    let t;
    if (fgRef.current && data?.nodes?.length > 0) {
      t = setTimeout(() => fgRef.current?.zoomToFit(400, 60), 300);
    }
    return () => { if (t) clearTimeout(t); };
  }, [data, dimensions]);

  // Compute Degree Centrality and Neighbors
  const graphData = useMemo(() => {
    const gData = (data?.nodes?.length > 0) ? data : EMPTY_GRAPH;

    gData.nodes.forEach(node => {
      node.neighbors = [];
      node.links = [];
      node.degree = 0;
    });

    gData.links.forEach(link => {
      const a = gData.nodes.find(n => n.id === link.source?.id || n.id === link.source);
      const b = gData.nodes.find(n => n.id === link.target?.id || n.id === link.target);

      if (a && b) {
        a.neighbors.push(b);
        b.neighbors.push(a);
        a.links.push(link);
        b.links.push(link);
        a.degree += 1;
        b.degree += 1;
      }
    });

    return gData;
  }, [data]);

  // Resolve an external highlight (from search) to a live node so we can center + glow it.
  const highlightedNode = useMemo(() => {
    if (!highlightNodeId) return null;
    return graphData.nodes.find(n => n.id === highlightNodeId) || null;
  }, [highlightNodeId, graphData]);

  useEffect(() => {
    if (highlightedNode) {
      const fg = fgRef.current;
      if (fg && highlightedNode.x !== undefined) {
        fg.centerAt(highlightedNode.x, highlightedNode.y, 600);
        fg.zoom(3, 600);
      }
    }
  }, [highlightedNode]);

  const isEmpty = graphData.nodes.length === 0;

  // --- Rendering Helpers ---
  const getNodeColorBase = useCallback((node) => {
    if (node.type === 'leak') {
      return node.risk >= 80 ? '255, 69, 58' : '255, 159, 10';
    }
    return node.isProtected ? '255, 214, 10' : '10, 132, 255';
  }, []);

  const getNodeSize = useCallback((node) => {
    const base = node.type === 'leak' ? 5 : 3;
    const scaling = Math.min((node.degree || 0) * 0.5, 8);
    return base + scaling;
  }, []);

  const handleNodeHover = useCallback((node) => {
    setHoverNode(node || null);
    if (containerRef.current) {
      containerRef.current.style.cursor = node ? 'pointer' : 'grab';
    }
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative border border-white/[0.08] bg-black/60 rounded-2xl overflow-hidden"
      style={{ minHeight: '500px' }}
    >
      {/* Legend */}
      <div className="absolute top-4 left-5 z-10 space-y-1 pointer-events-none">
        <p className="text-[13px] font-semibold text-white tracking-tight">Intelligence Topology</p>
        <p className="text-[11px] text-zinc-500">Interactive Force-Directed Graph</p>
      </div>

      {/* Color Legend */}
      <div className="absolute bottom-4 left-5 z-10 flex flex-wrap gap-x-5 gap-y-2 pointer-events-none">
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
          <span className="text-[11px] font-medium text-zinc-400 font-mono">
            {graphData.nodes.length} nodes · {graphData.links.length} links
          </span>
        </div>
      )}

      {/* State Machine */}
      {isLoading ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-[#0A84FF]">
          <div className="w-8 h-8 rounded-full border-2 border-transparent border-t-[#0A84FF] border-r-[#0A84FF] animate-spin shadow-[0_0_15px_rgba(10,132,255,0.4)]"></div>
          <p className="text-[12px] font-bold tracking-[0.2em] uppercase">Mapping Topology...</p>
        </div>
      ) : isEmpty ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-zinc-600">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="opacity-30">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
          </svg>
          <div className="text-center">
            <p className="text-[14px] font-medium text-zinc-500">No topology data</p>
            <p className="text-[12px] text-zinc-600 mt-1">Adjust the filters or click Re-Scan to populate the graph</p>
          </div>
        </div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          nodeLabel={(node) => `${node.label} ${node.degree ? `(${node.degree} connections)` : ''}`}
          nodeRelSize={1}
          onNodeClick={onNodeClick}
          onNodeHover={handleNodeHover}
          linkWidth={link => (hoverNode && (link.source === hoverNode || link.target === hoverNode)) ? 2 : 1}
          linkColor={link => {
            if (hoverNode) {
              const isHighlight = link.source === hoverNode || link.target === hoverNode;
              return isHighlight ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.02)';
            }
            return 'rgba(255,255,255,0.08)';
          }}
          linkDirectionalParticles={link => (hoverNode && (link.source === hoverNode || link.target === hoverNode)) ? 4 : 2}
          linkDirectionalParticleSpeed={0.004}
          backgroundColor="rgba(0,0,0,0)"
          nodeCanvasObject={(node, ctx, globalScale) => {
            const size = getNodeSize(node);
            const rgb = getNodeColorBase(node);

            const isSearchHit = highlightedNode && node.id === highlightedNode.id;

            // Focus mode dynamics
            let opacity = 1.0;
            let isHighlight = false;

            if (hoverNode) {
              if (node === hoverNode) {
                isHighlight = true;
              } else if (hoverNode.neighbors && hoverNode.neighbors.includes(node)) {
                isHighlight = true;
                opacity = 0.8;
              } else {
                opacity = 0.15;
              }
            }

            // Glow ring
            if (!hoverNode || isHighlight || isSearchHit) {
              ctx.beginPath();
              ctx.arc(node.x, node.y, size + (isSearchHit ? 6 : isHighlight ? 4 : 3), 0, 2 * Math.PI, false);
              ctx.fillStyle = isSearchHit
                ? `rgba(255, 255, 255, 0.35)`
                : `rgba(${rgb}, ${isHighlight ? 0.3 : 0.12})`;
              ctx.fill();
            }

            // Node core
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = `rgba(${rgb}, ${opacity})`;
            ctx.fill();

            // Labels: render above 1.6× zoom, or if highlighted/search hit
            if (globalScale > 1.6 || isHighlight || isSearchHit) {
              const label = node.label?.length > 25 ? node.label.slice(0, 25) + '…' : node.label;
              const fontSize = Math.min(12 / globalScale, isHighlight || isSearchHit ? 6 : 5);
              ctx.font = `${isHighlight || isSearchHit ? 'bold ' : ''}${fontSize}px -apple-system, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              ctx.fillStyle = `rgba(255, 255, 255, ${opacity * 0.92})`;
              ctx.fillText(label, node.x, node.y + size + 2);
            }
          }}
        />
      )}
    </div>
  );
});

export default NetworkGraphPro;
