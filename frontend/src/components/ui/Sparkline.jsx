import React from 'react';

/**
 * Minimal SVG sparkline — no recharts runtime, just a polyline.
 * `values`: array of numbers; `color`: stroke; renders into `width × height`.
 */
export default function Sparkline({ values = [], color = '#0A84FF', width = 80, height = 24, strokeWidth = 1.5, fill = true }) {
  if (!values.length) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const n = values.length;

  const points = values.map((v, i) => {
    const x = n === 1 ? width / 2 : (i / (n - 1)) * (width - strokeWidth) + strokeWidth / 2;
    const y = height - ((v - min) / range) * (height - strokeWidth) - strokeWidth / 2;
    return [x, y];
  });

  const pathD = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const areaD = `${pathD} L${points[points.length - 1][0].toFixed(2)},${height} L${points[0][0].toFixed(2)},${height} Z`;

  const gradId = `spark-grad-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      {fill && (
        <>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={areaD} fill={`url(#${gradId})`} />
        </>
      )}
      <path d={pathD} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
      {/* Last-point dot */}
      <circle
        cx={points[points.length - 1][0]}
        cy={points[points.length - 1][1]}
        r={2}
        fill={color}
      />
    </svg>
  );
}
