import React from 'react';
import { Button } from "@/components/ui/button";
import { Radar } from 'lucide-react';
import NetworkGraphPro from '../components/NetworkGraph';
import useNasoStore from '../store/useNasoStore';

export default function Topology() {
  const { graphData, fetchGraphData } = useNasoStore();

  return (
    <div className="h-[calc(100vh-110px)] flex flex-col gap-5">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-white">Intelligence Topology</h1>
          <p className="text-[13px] text-zinc-500 mt-0.5">Relationship map across cross-tenant artifacts</p>
        </div>
        <Button onClick={() => fetchGraphData()} className="h-9 px-5 text-[13px] font-medium bg-[#0A84FF] hover:bg-[#007AFF] text-white rounded-full shadow-sm">
          <Radar size={15} className="mr-2" strokeWidth={2} /> Re-Scan
        </Button>
      </div>
      <div className="flex-1 rounded-2xl border border-white/[0.08] bg-[#1C1C1E]/40 overflow-hidden">
          <NetworkGraphPro data={graphData} />
      </div>
    </div>
  );
}
