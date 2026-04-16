import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";

export const StatCard = ({ title, value, icon: Icon, description, trend, trendValue, color = 'blue-500' }) => (
  <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] shadow-sm relative overflow-hidden rounded-2xl transition-all duration-300 hover:bg-[#1C1C1E]/80">
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-[13px] font-medium text-zinc-400">
        {title}
      </CardTitle>
      <div className="p-1.5 rounded-full bg-white/[0.04]">
        <Icon className="h-4 w-4 text-zinc-300" strokeWidth={1.5} />
      </div>
    </CardHeader>
    <CardContent>
      <div className="flex items-baseline gap-2">
        <div className="text-3xl font-semibold tracking-tight text-white mb-1">{value}</div>
        {trend && (
          <span className={`flex items-center text-[12px] font-medium px-1.5 py-0.5 rounded-md ${trend === 'up' ? 'text-[#FF453A] bg-[#FF453A]/10' : 'text-[#32D74B] bg-[#32D74B]/10'}`}>
            {trend === 'up' ? <TrendingUp size={12} className="mr-1" strokeWidth={2.5}/> : <TrendingDown size={12} className="mr-1" strokeWidth={2.5}/>} 
            {trendValue}%
          </span>
        )}
      </div>
      <p className="text-[11px] text-zinc-500">
        {description}
      </p>
    </CardContent>
  </Card>
);
