import React, { useState, useRef, useEffect } from 'react';
import useNasoStore from '../store/useNasoStore';
import {
  Brain, Plus, Trash2, CheckCircle2, Circle, Clock, ChevronRight,
  Send, Loader2, Zap, Search, Database, Globe, AlertTriangle,
  FileText, X, ChevronDown, ChevronUp, Cpu, Wifi, WifiOff,
  MoreVertical, Archive, Target, Activity, Shield, Info,
  ClipboardList, Sparkles
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────────────────────

const TOOL_ICON = {
  search_identities: <Search size={12} strokeWidth={2} />,
  get_leaks: <Database size={12} strokeWidth={2} />,
  dark_web_probe: <Globe size={12} strokeWidth={2} />,
  get_identity_insights: <Target size={12} strokeWidth={2} />,
  create_task: <ClipboardList size={12} strokeWidth={2} />,
  flag_critical: <AlertTriangle size={12} strokeWidth={2} />,
};

const TOOL_LABEL = {
  search_identities: 'Searching identities',
  get_leaks: 'Querying leaks DB',
  dark_web_probe: 'Dark Web probe',
  get_identity_insights: 'Identity deep-scan',
  create_task: 'Creating task',
  flag_critical: 'Flagging leak',
};

const STATUS_COLOR = {
  pending: 'text-zinc-500',
  in_progress: 'text-[#0A84FF]',
  completed: 'text-[#32D74B]',
  failed: 'text-[#FF453A]',
};

const STATUS_ICON = {
  pending: <Circle size={12} strokeWidth={1.5} className="text-zinc-600" />,
  in_progress: <Clock size={12} strokeWidth={1.5} className="text-[#0A84FF]" />,
  completed: <CheckCircle2 size={12} strokeWidth={1.5} className="text-[#32D74B]" />,
  failed: <AlertTriangle size={12} strokeWidth={1.5} className="text-[#FF453A]" />,
};

function ToolCallBadge({ call, result }) {
  const [open, setOpen] = useState(false);
  const isLoading = !result;
  return (
    <div className="my-1">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all border ${
          isLoading
            ? 'bg-[#0A84FF]/10 border-[#0A84FF]/20 text-[#0A84FF]'
            : 'bg-white/[0.04] border-white/[0.06] text-zinc-400 hover:text-zinc-200'
        }`}
      >
        <span className={isLoading ? 'text-[#0A84FF]' : 'text-zinc-500'}>
          {isLoading ? <Loader2 size={12} className="animate-spin" /> : TOOL_ICON[call.name] || <Zap size={12} />}
        </span>
        <span>{TOOL_LABEL[call.name] || call.name}</span>
        {Object.keys(call.args || {}).length > 0 && (
          <span className="text-zinc-600 font-mono">
            {Object.entries(call.args).map(([k, v]) => `${k}="${v}"`).join(', ').slice(0, 40)}
          </span>
        )}
        {!isLoading && (open ? <ChevronUp size={11} /> : <ChevronDown size={11} />)}
      </button>
      {!isLoading && open && result?.data && (
        <div className="mt-1.5 ml-2 pl-3 border-l border-white/[0.06] text-[11px] font-mono text-zinc-500 max-h-32 overflow-y-auto">
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(result.data, null, 2).slice(0, 800)}
          </pre>
        </div>
      )}
    </div>
  );
}

function ChatBubble({ msg }) {
  const isUser = msg.role === 'user';
  const isAssistant = msg.role === 'assistant';
  const hasCalls = msg.toolCalls?.length > 0;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-4`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold ${
        isUser
          ? 'bg-[#0A84FF] text-white'
          : 'bg-white/[0.08] border border-white/[0.08] text-zinc-400'
      }`}>
        {isUser ? 'U' : <Brain size={13} strokeWidth={1.5} />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {/* Tool calls shown above text */}
        {hasCalls && (
          <div className="space-y-0.5 w-full">
            {msg.toolCalls.map((tc, i) => {
              const result = msg.toolResults?.find(r => r.id === tc.id);
              return <ToolCallBadge key={i} call={tc} result={result} />;
            })}
          </div>
        )}

        {/* Message text */}
        {(msg.content || msg.isError) && (
          <div className={`px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed whitespace-pre-wrap ${
            isUser
              ? 'bg-[#0A84FF] text-white rounded-tr-sm'
              : msg.isError
                ? 'bg-[#FF453A]/10 border border-[#FF453A]/20 text-[#FF453A] rounded-tl-sm'
                : 'bg-[#2C2C2E] text-zinc-200 rounded-tl-sm border border-white/[0.05]'
          }`}>
            {msg.content}
            {msg.role === 'assistant' && !msg.content && !hasCalls && (
              <span className="inline-flex gap-0.5 ml-1">
                <span className="w-1 h-1 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1 h-1 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1 h-1 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceCard({ item }) {
  const data = item.data;
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden mb-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-white/[0.03] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="p-1 rounded-md bg-[#0A84FF]/10 text-[#0A84FF]">
            {TOOL_ICON[item.name] || <Zap size={11} />}
          </span>
          <div>
            <p className="text-[12px] font-medium text-white">{TOOL_LABEL[item.name] || item.name}</p>
            {data.count !== undefined && (
              <p className="text-[10px] text-zinc-500">{data.count} result{data.count !== 1 ? 's' : ''}</p>
            )}
          </div>
        </div>
        {open ? <ChevronUp size={12} className="text-zinc-600" /> : <ChevronDown size={12} className="text-zinc-600" />}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-1.5 max-h-64 overflow-y-auto">
          {data.data?.slice(0, 8).map((row, i) => (
            <div key={i} className="px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.05]">
              {item.name === 'search_identities' && (
                <div className="flex items-center justify-between">
                  <p className="text-[12px] font-medium text-white">{row.identifier}</p>
                  <span className={`text-[11px] font-semibold ${row.risk_score >= 80 ? 'text-[#FF453A]' : row.risk_score >= 50 ? 'text-orange-400' : 'text-[#32D74B]'}`}>
                    {row.risk_score}
                  </span>
                </div>
              )}
              {item.name === 'get_leaks' && (
                <div className="flex items-center justify-between">
                  <p className="text-[12px] font-medium text-white">{row.source}</p>
                  <span className={`text-[11px] font-semibold ${row.severity >= 80 ? 'text-[#FF453A]' : row.severity >= 50 ? 'text-orange-400' : 'text-[#32D74B]'}`}>
                    {row.severity}
                  </span>
                </div>
              )}
              {item.name === 'dark_web_probe' && (
                <p className="text-[11px] text-zinc-400 truncate">{row.title || row.url || JSON.stringify(row)}</p>
              )}
              {!['search_identities', 'get_leaks', 'dark_web_probe'].includes(item.name) && (
                <p className="text-[11px] text-zinc-400 font-mono">{JSON.stringify(row).slice(0, 80)}</p>
              )}
            </div>
          ))}
          {data.error && <p className="text-[11px] text-[#FF453A] px-2">{data.error}</p>}
        </div>
      )}
    </div>
  );
}

function InvestigationPanel({ onSelectPlan, selectedPlanId }) {
  const {
    investigations, createInvestigation, deleteInvestigation, updateInvestigation,
    updateTask, addTaskToInvestigation, fetchInvestigations, activeInvestigationId, setActiveInvestigation
  } = useNasoStore();
  const [newTitle, setNewTitle] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [newTaskText, setNewTaskText] = useState('');
  const [addingTaskTo, setAddingTaskTo] = useState(null);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await createInvestigation(newTitle.trim());
    setNewTitle('');
    setShowNew(false);
  };

  const activePlan = investigations.find(p => p.id === activeInvestigationId);

  return (
    <div className="flex flex-col h-full min-w-0">
      {/* Header */}
      <div className="p-4 border-b border-white/[0.06]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ClipboardList size={15} strokeWidth={1.5} className="text-zinc-400" />
            <span className="text-[13px] font-semibold text-white">Investigations</span>
          </div>
          <button
            onClick={() => setShowNew(s => !s)}
            className="p-1.5 rounded-lg bg-[#0A84FF]/10 hover:bg-[#0A84FF]/20 text-[#0A84FF] transition-colors"
            title="New investigation"
          >
            <Plus size={13} strokeWidth={2} />
          </button>
        </div>

        {showNew && (
          <form onSubmit={handleCreate} className="flex gap-2">
            <input
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              placeholder="Investigation title..."
              autoFocus
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[12px] text-white placeholder-zinc-600 focus:outline-none focus:border-[#0A84FF]/50 focus:ring-0"
            />
            <button type="submit" className="px-3 py-1.5 bg-[#0A84FF] text-white rounded-lg text-[12px] font-medium hover:bg-[#0A84FF]/90 transition-colors">
              Create
            </button>
          </form>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {investigations.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 gap-3 text-center">
            <ClipboardList size={24} strokeWidth={1} className="text-zinc-700" />
            <p className="text-[12px] text-zinc-600">No investigations yet.<br/>Create one to start collaborating with AI.</p>
          </div>
        )}
        {investigations.map(plan => (
          <div key={plan.id} className={`rounded-xl border transition-all cursor-pointer ${
            activeInvestigationId === plan.id
              ? 'bg-[#0A84FF]/10 border-[#0A84FF]/30'
              : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]'
          }`}>
            <div
              className="p-3 flex items-start justify-between gap-2"
              onClick={() => setActiveInvestigation(plan.id === activeInvestigationId ? null : plan.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-white truncate">{plan.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    plan.status === 'completed' ? 'bg-[#32D74B]/10 text-[#32D74B]' :
                    plan.status === 'archived' ? 'bg-zinc-800 text-zinc-600' :
                    'bg-[#0A84FF]/10 text-[#0A84FF]'
                  }`}>{plan.status}</span>
                  <span className="text-[10px] text-zinc-600">{plan.completed_tasks}/{plan.task_count} tasks</span>
                </div>
              </div>
              <div className="flex gap-1 flex-shrink-0">
                <button
                  onClick={e => { e.stopPropagation(); updateInvestigation(plan.id, { status: 'completed' }); }}
                  className="p-1 rounded text-zinc-600 hover:text-[#32D74B] transition-colors"
                  title="Mark complete"
                ><CheckCircle2 size={12} strokeWidth={1.5} /></button>
                <button
                  onClick={e => { e.stopPropagation(); deleteInvestigation(plan.id); }}
                  className="p-1 rounded text-zinc-600 hover:text-[#FF453A] transition-colors"
                  title="Delete"
                ><Trash2 size={12} strokeWidth={1.5} /></button>
              </div>
            </div>

            {/* Tasks */}
            {activeInvestigationId === plan.id && plan.tasks && (
              <div className="border-t border-white/[0.06] px-3 pb-3 pt-2 space-y-1.5">
                {plan.tasks.map(task => (
                  <div key={task.id} className="flex items-start gap-2 group">
                    <button
                      onClick={() => updateTask(plan.id, task.id, {
                        status: task.status === 'completed' ? 'pending' : 'completed'
                      })}
                      className="flex-shrink-0 mt-0.5 transition-colors"
                    >
                      {STATUS_ICON[task.status] || STATUS_ICON.pending}
                    </button>
                    <p className={`text-[11px] flex-1 leading-tight ${
                      task.status === 'completed' ? 'text-zinc-600 line-through' : 'text-zinc-300'
                    }`}>{task.content}</p>
                    {task.created_by === 'ai' && (
                      <span className="flex-shrink-0 text-[9px] text-zinc-600 flex items-center gap-0.5">
                        <Sparkles size={9} strokeWidth={1.5} />AI
                      </span>
                    )}
                  </div>
                ))}

                {/* Add task */}
                {addingTaskTo === plan.id ? (
                  <div className="flex gap-1.5 mt-2">
                    <input
                      value={newTaskText}
                      onChange={e => setNewTaskText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && newTaskText.trim()) {
                          addTaskToInvestigation(plan.id, newTaskText.trim());
                          setNewTaskText('');
                          setAddingTaskTo(null);
                        }
                        if (e.key === 'Escape') setAddingTaskTo(null);
                      }}
                      placeholder="New task... (Enter to save)"
                      autoFocus
                      className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-[11px] text-white placeholder-zinc-600 focus:outline-none focus:border-[#0A84FF]/40"
                    />
                    <button onClick={() => setAddingTaskTo(null)} className="p-1 text-zinc-600 hover:text-zinc-400">
                      <X size={11} strokeWidth={2} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingTaskTo(plan.id)}
                    className="flex items-center gap-1.5 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors mt-1"
                  >
                    <Plus size={11} strokeWidth={2} /> Add task
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main AiAssistant component ────────────────────────────────────────────────

export default function AiAssistant() {
  const {
    chatHistory, sendAiMessage, isAiStreaming, clearChatHistory,
    investigations, fetchInvestigations, activeInvestigationId,
    checkAiHealth, aiStatus, evidencePanel, clearEvidencePanel,
  } = useNasoStore();

  const [input, setInput] = useState('');
  const [showEvidence, setShowEvidence] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const activePlan = investigations.find(p => p.id === activeInvestigationId);

  useEffect(() => {
    fetchInvestigations();
    checkAiHealth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const handleSend = async () => {
    if (!input.trim() || isAiStreaming) return;
    const msg = input.trim();
    setInput('');
    await sendAiMessage(msg);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const STARTERS = [
    'Find all critical breaches discovered this week',
    'Investigate identity john@example.com',
    'Search dark web for leaked credentials',
    'Create an investigation plan for a phishing campaign',
  ];

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left: Investigation Plans ─────────────────────────────── */}
      <div className="w-[240px] flex-shrink-0 border-r border-white/[0.06] flex flex-col">
        <InvestigationPanel />
      </div>

      {/* ── Center: Chat ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Chat header */}
        <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-xl bg-[#0A84FF]/10 border border-[#0A84FF]/20">
              <Brain size={16} strokeWidth={1.5} className="text-[#0A84FF]" />
            </div>
            <div>
              <p className="text-[14px] font-semibold text-white">NASO Co-Analyst</p>
              <div className="flex items-center gap-1.5">
                {aiStatus === 'online'
                  ? <><Wifi size={10} className="text-[#32D74B]" /><span className="text-[10px] text-[#32D74B]">AI online</span></>
                  : aiStatus === 'offline'
                    ? <><WifiOff size={10} className="text-[#FF453A]" /><span className="text-[10px] text-[#FF453A]">AI offline</span></>
                    : <span className="text-[10px] text-zinc-600">Checking AI...</span>
                }
                {activePlan && (
                  <>
                    <span className="text-zinc-700">·</span>
                    <span className="text-[10px] text-[#0A84FF] truncate max-w-[120px]">{activePlan.title}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowEvidence(s => !s)}
              className="px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-zinc-400 hover:text-white hover:bg-white/[0.06] border border-white/[0.06] transition-colors flex items-center gap-1.5"
            >
              <Activity size={12} strokeWidth={1.5} />
              Evidence {showEvidence ? 'on' : 'off'}
            </button>
            <button
              onClick={clearChatHistory}
              className="p-1.5 rounded-lg text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.06] transition-colors"
              title="Clear chat"
            >
              <Trash2 size={13} strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {chatHistory.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
              <div className="p-4 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/20">
                <Brain size={32} strokeWidth={1} className="text-[#0A84FF]" />
              </div>
              <div>
                <p className="text-[15px] font-semibold text-white mb-1">NASO Co-Analyst</p>
                <p className="text-[13px] text-zinc-500 max-w-sm">
                  Your AI forensic partner. I can search identities, query breaches, probe the dark web, and build investigation plans — in real-time.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 w-full max-w-md">
                {STARTERS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(s); textareaRef.current?.focus(); }}
                    className="px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-left text-[12px] text-zinc-400 hover:text-white hover:bg-white/[0.06] hover:border-white/[0.10] transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {chatHistory.map((msg) => (
            <ChatBubble key={msg.id} msg={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="px-5 py-4 border-t border-white/[0.06] flex-shrink-0">
          <div className="flex items-end gap-3 bg-[#2C2C2E]/60 border border-white/[0.08] rounded-2xl px-4 py-3 focus-within:border-[#0A84FF]/40 transition-colors">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask NASO Co-Analyst... ${activePlan ? `(Investigation: ${activePlan.title})` : '(no investigation selected)'}`}
              rows={1}
              disabled={isAiStreaming}
              className="flex-1 bg-transparent text-[13px] text-white placeholder-zinc-600 focus:outline-none resize-none leading-relaxed min-h-[22px] max-h-[120px] overflow-y-auto disabled:opacity-50"
              style={{ scrollbarWidth: 'none' }}
            />
            <button
              onClick={handleSend}
              disabled={isAiStreaming || !input.trim()}
              className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                isAiStreaming || !input.trim()
                  ? 'bg-white/[0.04] text-zinc-600 cursor-not-allowed'
                  : 'bg-[#0A84FF] text-white hover:bg-[#0A84FF]/90 shadow-lg shadow-[#0A84FF]/20'
              }`}
            >
              {isAiStreaming
                ? <Loader2 size={14} className="animate-spin" strokeWidth={2} />
                : <Send size={14} strokeWidth={2} />
              }
            </button>
          </div>
          <p className="text-[10px] text-zinc-700 text-center mt-2">
            Press Enter to send · Shift+Enter for new line · AI may execute real NASO tools
          </p>
        </div>
      </div>

      {/* ── Right: Evidence panel ─────────────────────────────────── */}
      {showEvidence && (
        <div className="w-[260px] flex-shrink-0 border-l border-white/[0.06] flex flex-col">
          <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={14} strokeWidth={1.5} className="text-zinc-400" />
              <span className="text-[13px] font-semibold text-white">Evidence</span>
            </div>
            {evidencePanel.length > 0 && (
              <button onClick={clearEvidencePanel} className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors">
                Clear
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {evidencePanel.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 gap-3 text-center">
                <Database size={20} strokeWidth={1} className="text-zinc-700" />
                <p className="text-[11px] text-zinc-600">
                  Tool results and evidence will appear here as the AI gathers intelligence.
                </p>
              </div>
            ) : (
              evidencePanel.map((item, i) => <EvidenceCard key={i} item={item} />)
            )}
          </div>
        </div>
      )}
    </div>
  );
}
