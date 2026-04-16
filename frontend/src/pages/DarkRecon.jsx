import React, { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Radar, ShieldAlert, ExternalLink, Loader2 } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';

export default function DarkRecon({ reconQuery, setReconQuery }) {
  const { darkWebResults, searchDarkWeb, isLoading, error } = useNasoStore();
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = () => {
    setHasSearched(true);
    searchDarkWeb(reconQuery);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-white">Dark Recon Probe</h1>
        <p className="text-[13px] text-zinc-500 mt-0.5">Scrutinize encrypted databases and active .onion services</p>
      </div>

      <Card className="bg-[#1C1C1E]/50 backdrop-blur-xl border-white/[0.08] rounded-2xl overflow-hidden">
        <CardContent className="p-8">
          <div className="flex flex-col items-center gap-8 max-w-2xl mx-auto">
            <div className="p-5 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/20">
                <Radar size={48} className="text-[#0A84FF]" strokeWidth={1.5} />
            </div>
            <div className="space-y-2 text-center">
                <h2 className="text-[20px] font-semibold tracking-tight text-white">Onion Intelligence Probe</h2>
                <p className="text-[13px] text-zinc-500 max-w-md mx-auto leading-relaxed">Search encrypted databases and .onion services for forensic identifiers, emails, hashes, or signatures.</p>
            </div>
            <div className="w-full flex gap-3 p-2 pl-4 bg-black/40 rounded-full border border-white/[0.08] focus-within:border-[#0A84FF]/50 transition-all">
                <input 
                    type="text" 
                    placeholder="Signature, email, or hash..."
                    value={reconQuery}
                    onChange={(e) => setReconQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && reconQuery && !isLoading) {
                        handleSearch();
                      }
                    }}
                    disabled={isLoading}
                    className="flex-1 bg-transparent text-[14px] text-white placeholder:text-zinc-600 outline-none"
                />
                <Button disabled={isLoading || !reconQuery} onClick={handleSearch} className="bg-[#0A84FF] hover:bg-[#007AFF] text-white font-medium text-[13px] px-6 rounded-full h-10 shadow-sm">
                    {isLoading ? <Loader2 size={15} className="animate-spin" /> : 'Launch Probe'}
                </Button>
            </div>
            <div className="flex gap-6 text-[11px] font-medium text-zinc-500">
                <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#32D74B]"></div> Ahmia Active</span>
                <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]"></div> Tor Circuit On</span>
                <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]"></div> Correlation On</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl border border-[#FF453A]/30 bg-[#FF453A]/10 text-[#FF453A] flex items-center gap-3">
          <ShieldAlert size={20} />
          <div>
            <p className="font-semibold text-[13px] uppercase tracking-wider">Node Offline</p>
            <p className="text-[12px]">{error}</p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && hasSearched && darkWebResults.length === 0 && !error && (
          <div className="p-10 border border-white/[0.05] bg-black/20 rounded-2xl flex flex-col items-center justify-center text-zinc-500">
             <Radar size={40} className="opacity-30 mb-4" strokeWidth={1.5} />
             <p className="text-[14px] font-medium tracking-wide uppercase text-white">No Intel Found</p>
             <p className="text-[12px] mt-2">The target probe yielded no dark web artifacts for this signature.</p>
          </div>
      )}

      {darkWebResults.length > 0 && (
          <div className="space-y-4">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                  <h3 className="text-[14px] font-semibold text-white flex items-center gap-2">
                      <ShieldAlert size={16} className="text-[#FF453A]" strokeWidth={1.5} /> Intercepted Intel ({darkWebResults.length})
                  </h3>
                  <Button variant="ghost" onClick={() => useNasoStore.setState({ darkWebResults: [] })} className="text-[12px] font-medium text-zinc-500 hover:text-white h-8 rounded-full px-3">Clear Results</Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {darkWebResults.map((res, i) => (
                      <Card key={i} className="bg-[#1C1C1E]/50 border-white/[0.08] p-5 hover:border-white/[0.15] transition-all rounded-2xl">
                          <div className="flex justify-between items-start mb-4">
                              <Badge className="bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 font-medium text-[10px]">Match Found</Badge>
                              <ExternalLink size={15} className="text-zinc-600 hover:text-white transition-colors cursor-pointer" strokeWidth={1.5} />
                          </div>
                          <h4 className="text-[15px] font-semibold text-white mb-2 tracking-tight">{res.title}</h4>
                          <p className="text-[11px] font-mono text-zinc-500 break-all bg-black/30 p-3 rounded-lg border border-white/[0.05]">{res.url}</p>
                          <div className="flex gap-2 mt-4">
                              <Button className="flex-1 text-[12px] font-medium bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 hover:bg-[#0A84FF]/20 transition-all rounded-full h-9">Deep Scrape</Button>
                              <Button variant="ghost" className="text-[12px] font-medium border border-white/10 rounded-full h-9 px-4 text-zinc-400 hover:text-white">Proxy Link</Button>
                          </div>
                      </Card>
                  ))}
              </div>
          </div>
      )}
    </div>
  );
}
