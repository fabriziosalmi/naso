import React, { useEffect, useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Radar, ShieldAlert, ExternalLink, Loader2, Copy, Check, Globe, Database, Zap } from 'lucide-react';
import useNasoStore from '../store/useNasoStore';
import { toast } from '../store/useToastStore';
import { Input } from '../components/ui/Input';

const PROBE_STAGES = [
  'Opening Tor circuit',
  'Querying Ahmia index',
  'Fetching .onion descriptors',
  'Correlating against breach database',
  'Ranking artifacts',
];

function hostnameFromOnion(url) {
  if (!url) return '';
  try {
    const u = new URL(url.startsWith('http') ? url : `http://${url}`);
    return u.hostname;
  } catch {
    return url.split('/')[0];
  }
}

function ResultCard({ result }) {
  const [copied, setCopied] = useState(false);
  const host = hostnameFromOnion(result.url);

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(result.url);
      setCopied(true);
      toast.success('URL copied', host);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Copy failed');
    }
  };

  return (
    <Card className="bg-[#1C1C1E]/50 border-white/[0.08] p-5 hover:border-white/[0.15] transition-all rounded-2xl">
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#0A84FF]/10 border border-[#0A84FF]/20 flex items-center justify-center shrink-0">
            <Globe size={14} className="text-[#0A84FF]" strokeWidth={1.8} />
          </div>
          <Badge className="bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 font-medium text-[10px]">Match Found</Badge>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={copyUrl}
            title="Copy URL"
            aria-label="Copy onion URL"
            className="p-1.5 rounded-md text-zinc-500 hover:text-white hover:bg-white/10 transition-colors"
          >
            {copied ? <Check size={14} className="text-[#32D74B]" /> : <Copy size={14} strokeWidth={1.8} />}
          </button>
          <ExternalLink size={15} className="text-zinc-600 hover:text-white transition-colors cursor-pointer" strokeWidth={1.5} />
        </div>
      </div>
      <h4 className="text-[15px] font-semibold text-white mb-2 tracking-tight">{result.title}</h4>
      <p className="text-[11px] font-mono text-zinc-500 break-all bg-black/30 p-3 rounded-lg border border-white/[0.05]">
        {result.url}
      </p>
      <div className="flex gap-2 mt-4">
        <Button className="flex-1 text-[12px] font-medium bg-[#0A84FF]/10 text-[#0A84FF] border border-[#0A84FF]/20 hover:bg-[#0A84FF]/20 transition-all rounded-full h-9">Deep Scrape</Button>
        <Button variant="ghost" className="text-[12px] font-medium border border-white/10 rounded-full h-9 px-4 text-zinc-400 hover:text-white">Proxy Link</Button>
      </div>
    </Card>
  );
}

export default function DarkRecon({ reconQuery, setReconQuery }) {
  const { darkWebResults, darkWebReport, searchDarkWeb, isLoading, error } = useNasoStore();
  const [hasSearched, setHasSearched] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);

  // Rotate through probe stages while loading, for tactical "something is happening" feedback.
  useEffect(() => {
    if (!isLoading) { setStageIndex(0); return; }
    setStageIndex(0);
    const t = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, PROBE_STAGES.length - 1));
    }, 900);
    return () => clearInterval(t);
  }, [isLoading]);

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
            <div className="p-5 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/20 relative">
              {isLoading && (
                <span className="absolute inset-0 rounded-2xl border-2 border-[#0A84FF]/40 animate-ping" />
              )}
              <Radar size={48} className="text-[#0A84FF]" strokeWidth={1.5} />
            </div>
            <div className="space-y-2 text-center">
              <h2 className="text-[20px] font-semibold tracking-tight text-white">Onion Intelligence Probe</h2>
              <p className="text-[13px] text-zinc-500 max-w-md mx-auto leading-relaxed">
                Search encrypted databases and .onion services for forensic identifiers, emails, hashes, or signatures.
              </p>
            </div>
            <div className="w-full flex gap-3 p-2 pl-4 bg-black/40 rounded-full border border-white/[0.08] focus-within:border-[#0A84FF]/50 transition-all">
              <input
                type="text"
                placeholder="Signature, email, or hash..."
                value={reconQuery}
                onChange={(e) => setReconQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && reconQuery && !isLoading) handleSearch();
                }}
                disabled={isLoading}
                aria-label="Probe search query"
                className="flex-1 bg-transparent text-[14px] text-white placeholder:text-zinc-600 outline-none"
              />
              <Button
                disabled={isLoading || !reconQuery}
                onClick={handleSearch}
                className="bg-[#0A84FF] hover:bg-[#007AFF] text-white font-medium text-[13px] px-6 rounded-full h-10 shadow-sm"
              >
                {isLoading ? <Loader2 size={15} className="animate-spin" /> : 'Launch Probe'}
              </Button>
            </div>

            {/* Probe progress stepper */}
            {isLoading && (
              <div className="w-full max-w-md space-y-2" aria-live="polite">
                {PROBE_STAGES.map((label, i) => {
                  const done = i < stageIndex;
                  const active = i === stageIndex;
                  return (
                    <div
                      key={label}
                      className={`flex items-center gap-3 text-[12px] transition-colors ${
                        done ? 'text-[#32D74B]' : active ? 'text-[#0A84FF]' : 'text-zinc-600'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        done ? 'bg-[#32D74B]' : active ? 'bg-[#0A84FF] animate-pulse' : 'bg-zinc-700'
                      }`} />
                      <span className="font-mono uppercase tracking-wider text-[10px]">{label}</span>
                      {active && <Loader2 size={11} className="animate-spin ml-auto" />}
                      {done && <Check size={11} className="ml-auto" />}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Three green and blue dots reading "Ahmia Active · Tor Circuit
                On · Correlation On" used to sit here, and none of them was
                connected to anything: they said On with the Tor cluster in a
                crash loop. Nothing in the API reports Tor or Ahmia
                reachability, so there is nothing honest to put in their place —
                the probe result below is the real status, and it arrives when
                you run one. */}
            <p className="text-[11px] font-medium text-zinc-500">
              Queries route through the Tor cluster. A probe that cannot reach it fails loudly rather than
              returning nothing.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && !isLoading && (
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
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-white/[0.06]">
                  <div className="flex items-center gap-3 flex-wrap">
                      <h3 className="text-[14px] font-semibold text-white flex items-center gap-2">
                          <ShieldAlert size={16} className="text-[#FF453A]" strokeWidth={1.5} /> Intercepted Intel ({darkWebResults.length})
                      </h3>
                      {/* Provenance chips — surfaced from the backend report so
                          operators know if results came from cache, how many
                          Ahmia pages we paged through, and whether Tor circuits
                          were rotated for this probe. */}
                      {darkWebReport?.cached && (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#FFD60A]/10 border border-[#FFD60A]/20 text-[10px] font-medium text-[#FFD60A]">
                              <Database size={10} strokeWidth={2} /> From cache
                          </span>
                      )}
                      {darkWebReport?.pages_fetched > 0 && (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-[10px] font-medium text-zinc-400">
                              {darkWebReport.pages_fetched} page{darkWebReport.pages_fetched === 1 ? '' : 's'}
                              {darkWebReport.duplicates_dropped > 0 && (
                                <span className="text-zinc-600"> · −{darkWebReport.duplicates_dropped} dup</span>
                              )}
                          </span>
                      )}
                      {darkWebReport?.rotation && Object.keys(darkWebReport.rotation).length > 0 && (
                          <span
                            title={Object.entries(darkWebReport.rotation).map(([h, s]) => `${h}: ${s}`).join('\n')}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#0A84FF]/10 border border-[#0A84FF]/20 text-[10px] font-medium text-[#0A84FF] cursor-help"
                          >
                              <Zap size={10} strokeWidth={2} /> {Object.keys(darkWebReport.rotation).length} circuits rotated
                          </span>
                      )}
                      {typeof darkWebReport?.elapsed_seconds === 'number' && !darkWebReport.cached && (
                          <span className="text-[10px] font-mono text-zinc-600">
                              {darkWebReport.elapsed_seconds.toFixed(2)}s
                          </span>
                      )}
                  </div>
                  <Button variant="ghost" onClick={() => useNasoStore.setState({ darkWebResults: [], darkWebReport: null })} className="text-[12px] font-medium text-zinc-500 hover:text-white h-8 rounded-full px-3 self-start sm:self-auto">Clear Results</Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {darkWebResults.map((res, i) => <ResultCard key={i} result={res} />)}
              </div>
          </div>
      )}
    </div>
  );
}
