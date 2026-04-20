import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useCountUp } from "@/lib/useCountUp";
import Sparkline from "@/components/ui/Sparkline";

/**
 * Compute a % delta between the last bucket and the prior average.
 * Returns { pct, direction } where pct is absolute (0–999) and direction in
 * 'up' | 'down' | 'flat'. Flat when either side is zero or delta < 5%.
 */
function deriveTrend(series) {
  if (!Array.isArray(series) || series.length < 2) return { pct: null, direction: 'flat' };
  const last = series[series.length - 1];
  const prior = series.slice(0, -1);
  const priorAvg = prior.reduce((a, b) => a + b, 0) / prior.length;
  if (priorAvg === 0 && last === 0) return { pct: 0, direction: 'flat' };
  if (priorAvg === 0) return { pct: 100, direction: 'up' };
  const pct = Math.round(((last - priorAvg) / priorAvg) * 100);
  const absPct = Math.abs(pct);
  if (absPct < 5) return { pct: absPct, direction: 'flat' };
  return { pct: Math.min(absPct, 999), direction: pct > 0 ? 'up' : 'down' };
}

export const StatCard = ({ title, value, icon: Icon, description, series, invertTrend = false, sparkColor = '#0A84FF' }) => {
  const isNumeric = typeof value === 'number';
  const displayed = useCountUp(isNumeric ? value : 0);
  const rendered = isNumeric ? displayed.toLocaleString() : value;

  const trend = deriveTrend(series);
  // For "good-when-low" metrics (e.g. infra load) we flip the semantic color.
  const isBad = invertTrend ? trend.direction === 'down' : trend.direction === 'up';
  const tone =
    trend.direction === 'flat' ? 'text-zinc-400 bg-white/[0.05]' :
    isBad ? 'text-[#FF453A] bg-[#FF453A]/10' : 'text-[#32D74B] bg-[#32D74B]/10';

  const TrendIcon = trend.direction === 'up' ? TrendingUp : trend.direction === 'down' ? TrendingDown : Minus;

  return (
    <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] shadow-sm relative overflow-hidden rounded-2xl transition-all duration-300 hover:bg-[#1C1C1E]/80 group">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-[13px] font-medium text-zinc-400">
          {title}
        </CardTitle>
        <div className="p-1.5 rounded-full bg-white/[0.04] transition-colors group-hover:bg-white/[0.08]">
          <Icon className="h-4 w-4 text-zinc-300" strokeWidth={1.5} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <div className="text-3xl font-semibold tracking-tight text-white mb-1 tabular-nums">{rendered}</div>
              {trend.pct !== null && (
                <span className={`flex items-center text-[11px] font-medium px-1.5 py-0.5 rounded-md ${tone}`}>
                  <TrendIcon size={11} className="mr-0.5" strokeWidth={2.5} />
                  {trend.direction === 'flat' ? '±0' : `${trend.pct}%`}
                </span>
              )}
            </div>
            <p className="text-[11px] text-zinc-500 truncate">{description}</p>
          </div>
          {series && series.length > 1 && (
            <div className="shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
              <Sparkline values={series} color={sparkColor} width={80} height={28} />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
