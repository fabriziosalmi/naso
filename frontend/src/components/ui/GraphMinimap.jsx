import React, { useEffect, useRef } from 'react';

/**
 * Lightweight minimap for ForceGraph2D. Draws every node scaled into a small
 * canvas, overlays the current viewport rectangle, and lets the operator pan
 * by clicking anywhere inside the map.
 *
 * Props:
 *   graphData     { nodes, links } — already laid out (nodes have x/y)
 *   fgApi         imperative handle exposing { centerOn: (node) }
 *   forceGraphRef raw ref to <ForceGraph2D> for reading zoom() + centerAt
 */
const WIDTH = 180;
const HEIGHT = 120;
const PAD = 6;

function colorOf(node) {
  if (node.type === 'leak') {
    return node.risk >= 80 ? '#FF453A' : '#FF9F0A';
  }
  return node.isProtected ? '#FFD60A' : '#0A84FF';
}

export default function GraphMinimap({ graphData, forceGraphRef }) {
  const canvasRef = useRef(null);
  const lastBoundsRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    if (!graphData?.nodes?.length) {
      // Clear on empty data.
      const ctx = canvasRef.current.getContext('2d');
      ctx.clearRect(0, 0, WIDTH, HEIGHT);
      lastBoundsRef.current = null;
      return;
    }

    // We repaint on every animation frame while the forceGraph layout runs —
    // nodes have x/y that change over time. Stop when component unmounts.
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');

      // Compute bbox from node positions.
      const nodes = graphData.nodes.filter(n => n.x !== undefined && n.y !== undefined);
      if (!nodes.length) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      nodes.forEach(n => {
        if (n.x < minX) minX = n.x;
        if (n.x > maxX) maxX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.y > maxY) maxY = n.y;
      });
      // Guard degenerate bbox (single node / collapsed layout).
      if (!Number.isFinite(minX) || minX === maxX) { minX -= 10; maxX += 10; }
      if (!Number.isFinite(minY) || minY === maxY) { minY -= 10; maxY += 10; }

      const w = maxX - minX;
      const h = maxY - minY;
      // Preserve aspect ratio by scaling uniformly to the smaller dimension.
      const scale = Math.min((WIDTH - PAD * 2) / w, (HEIGHT - PAD * 2) / h);
      const offsetX = PAD + ((WIDTH - PAD * 2) - w * scale) / 2;
      const offsetY = PAD + ((HEIGHT - PAD * 2) - h * scale) / 2;
      const project = (x, y) => [offsetX + (x - minX) * scale, offsetY + (y - minY) * scale];

      lastBoundsRef.current = { minX, maxX, minY, maxY, scale, offsetX, offsetY };

      // Clear + backdrop
      ctx.clearRect(0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(0, 0, WIDTH, HEIGHT);

      // Links faint
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 0.5;
      (graphData.links || []).forEach(l => {
        const a = typeof l.source === 'object' ? l.source : null;
        const b = typeof l.target === 'object' ? l.target : null;
        if (!a || !b || a.x === undefined || b.x === undefined) return;
        const [ax, ay] = project(a.x, a.y);
        const [bx, by] = project(b.x, b.y);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      });

      // Nodes
      nodes.forEach(n => {
        const [x, y] = project(n.x, n.y);
        const r = n.type === 'leak' ? 1.8 : 1.4;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = colorOf(n);
        ctx.fill();
      });

      // Viewport rectangle (fg screen → graph coords).
      const fg = forceGraphRef?.current;
      if (fg && typeof fg.screen2GraphCoords === 'function') {
        try {
          // Find the ForceGraph's real canvas — it's a sibling of our
          // minimap wrapper inside the Topology container. Exclude ourselves.
          const outer = canvas.parentElement?.parentElement;
          const graphCanvas = outer
            ? Array.from(outer.querySelectorAll('canvas')).find(c => c !== canvas)
            : null;
          const graphBox = graphCanvas?.getBoundingClientRect?.();
          if (graphBox && graphBox.width > 0) {
            const tl = fg.screen2GraphCoords(graphBox.left, graphBox.top);
            const br = fg.screen2GraphCoords(graphBox.right, graphBox.bottom);
            const [px1, py1] = project(tl.x, tl.y);
            const [px2, py2] = project(br.x, br.y);
            ctx.strokeStyle = 'rgba(10,132,255,0.9)';
            ctx.lineWidth = 1;
            ctx.strokeRect(
              Math.max(0, px1),
              Math.max(0, py1),
              Math.min(WIDTH, px2) - Math.max(0, px1),
              Math.min(HEIGHT, py2) - Math.max(0, py1),
            );
          }
        } catch { /* screen2GraphCoords may not be ready yet */ }
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [graphData, forceGraphRef]);

  // Click-to-pan: translate click into graph coords and ask fg to center there.
  const handleClick = (e) => {
    const canvas = canvasRef.current;
    const bounds = lastBoundsRef.current;
    const fg = forceGraphRef?.current;
    if (!canvas || !bounds || !fg || typeof fg.centerAt !== 'function') return;

    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;

    const { minX, minY, scale, offsetX, offsetY } = bounds;
    const gx = minX + (cx - offsetX) / scale;
    const gy = minY + (cy - offsetY) / scale;

    fg.centerAt(gx, gy, 400);
  };

  const nodeCount = graphData?.nodes?.length ?? 0;
  if (nodeCount === 0) return null;

  return (
    <div
      className="absolute bottom-4 right-4 z-10 rounded-xl border border-white/[0.08] bg-black/60 backdrop-blur-xl overflow-hidden shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
      aria-hidden="true"
    >
      <div className="flex items-center justify-between px-2.5 py-1 border-b border-white/[0.05]">
        <span className="text-[9px] uppercase tracking-[0.2em] text-zinc-500 font-medium">Minimap</span>
        <span className="text-[9px] font-mono text-zinc-600">{nodeCount}</span>
      </div>
      <canvas
        ref={canvasRef}
        width={WIDTH}
        height={HEIGHT}
        onClick={handleClick}
        className="block cursor-crosshair"
      />
    </div>
  );
}
