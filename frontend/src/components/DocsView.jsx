import React, { useState, useMemo } from 'react';
import {
  BookOpen, Search, ChevronRight, Terminal, Shield, Users,
  Activity, Globe, ScrollText, Brain, Code2, Zap, Database,
  Lock, Target, Workflow, AlertTriangle, Info, CheckCircle2,
  Network, Fingerprint, FileText, Settings, Key, Server
} from 'lucide-react';

// ── Content definition ───────────────────────────────────────────────────────

const CODE = (str) => (
  <code className="px-1.5 py-0.5 rounded-md bg-white/[0.06] border border-white/[0.06] font-mono text-[11px] text-[#0A84FF]">{str}</code>
);

const BLOCK = ({ code, lang = '' }) => (
  <div className="rounded-xl bg-[#161618] border border-white/[0.06] overflow-hidden my-3">
    {lang && <div className="px-4 py-2 border-b border-white/[0.05] text-[10px] font-mono text-zinc-600 uppercase">{lang}</div>}
    <pre className="p-4 text-[12px] font-mono text-zinc-300 overflow-x-auto whitespace-pre leading-relaxed">{code}</pre>
  </div>
);

const Note = ({ children, type = 'info' }) => {
  const styles = {
    info: 'bg-[#0A84FF]/08 border-[#0A84FF]/25 text-[#0A84FF]',
    warn: 'bg-[#FF9F0A]/08 border-[#FF9F0A]/25 text-[#FF9F0A]',
    danger: 'bg-[#FF453A]/08 border-[#FF453A]/25 text-[#FF453A]',
    success: 'bg-[#32D74B]/08 border-[#32D74B]/25 text-[#32D74B]',
  };
  const icons = { info: Info, warn: AlertTriangle, danger: AlertTriangle, success: CheckCircle2 };
  const Icon = icons[type];
  return (
    <div className={`flex gap-3 rounded-xl border p-3.5 my-3 ${styles[type]}`}>
      <Icon size={15} strokeWidth={1.5} className="flex-shrink-0 mt-0.5" />
      <p className="text-[12px] leading-relaxed">{children}</p>
    </div>
  );
};

const H2 = ({ children }) => (
  <h2 className="text-[18px] font-semibold text-white mt-8 mb-4 pb-3 border-b border-white/[0.06] tracking-tight">{children}</h2>
);

const H3 = ({ children }) => (
  <h3 className="text-[14px] font-semibold text-zinc-200 mt-5 mb-2">{children}</h3>
);

const P = ({ children }) => (
  <p className="text-[13px] text-zinc-400 leading-relaxed mb-3">{children}</p>
);

const Li = ({ children }) => (
  <li className="flex items-start gap-2 text-[13px] text-zinc-400 mb-1.5">
    <ChevronRight size={13} strokeWidth={2} className="flex-shrink-0 mt-0.5 text-zinc-600" />
    <span>{children}</span>
  </li>
);

const Table = ({ headers, rows }) => (
  <div className="rounded-xl border border-white/[0.07] overflow-hidden my-3">
    <table className="w-full text-[12px]">
      <thead>
        <tr className="border-b border-white/[0.07] bg-white/[0.02]">
          {headers.map((h, i) => <th key={i} className="px-4 py-2.5 text-left font-semibold text-zinc-400">{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-white/[0.04] hover:bg-white/[0.02] last:border-0">
            {row.map((cell, j) => <td key={j} className="px-4 py-2.5 text-zinc-400">{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const SECTIONS = [
  {
    id: 'getting-started',
    label: 'Getting Started',
    icon: Zap,
    content: (
      <>
        <H2>Getting Started with NASO</H2>
        <P>NASO (Network Analytics & SOC Operations) is a professional forensic intelligence platform designed for enterprise threat analysts. It provides real-time breach monitoring, identity correlation, dark web reconnaissance, and AI-powered investigation workflows.</P>

        <H3>Architecture Overview</H3>
        <Table
          headers={['Component', 'Technology', 'Role']}
          rows={[
            ['API Backend', 'FastAPI + SQLAlchemy', 'Core data layer, auth, business logic'],
            ['Message Queue', 'RabbitMQ + Celery', 'Async workers for scanning, AI processing'],
            ['Search Index', 'Elasticsearch', 'Full-text search across breach data'],
            ['Object Store', 'MinIO', 'Forensic screenshots and artifacts'],
            ['AI Engine', 'LM Studio (local LLM)', 'Co-Analyst chat and tool calling'],
            ['Frontend', 'React + Vite + Tailwind', 'Dashboard UI'],
          ]}
        />

        <H3>First Login</H3>
        <P>Navigate to the NASO dashboard. Use your assigned credentials (email + password) issued by your system administrator. Tokens expire after 60 minutes and are automatically invalidated on logout.</P>
        <Note type="info">All actions are logged in the Audit trail. Analysts cannot delete audit records.</Note>

        <H3>First Steps</H3>
        <ul className="space-y-1 mb-3">
          <Li>Add a monitored identity in <strong className="text-zinc-200">Master Identities → Add Identity</strong></Li>
          <Li>Navigate to <strong className="text-zinc-200">Neural Topology</strong> to see the correlation graph</Li>
          <Li>Use <strong className="text-zinc-200">Dark Recon</strong> to probe a keyword against the dark web</Li>
          <Li>Open <strong className="text-zinc-200">AI Co-Analyst</strong> to start a collaborative investigation</Li>
        </ul>
      </>
    ),
  },
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: Activity,
    content: (
      <>
        <H2>Dashboard</H2>
        <P>The main dashboard provides a real-time overview of your forensic environment. Data auto-refreshes every 30 seconds.</P>

        <H3>Stat Cards</H3>
        <Table
          headers={['Card', 'Description']}
          rows={[
            ['Total Leaks', 'All breach records ingested for your tenant'],
            ['Critical Alerts', 'Leaks with severity score ≥ 80'],
            ['Identities Monitored', 'Active master identities under observation'],
            ['System Status', 'Backend health and latency'],
          ]}
        />

        <H3>Severity Timeline</H3>
        <P>The area chart shows breach discovery rate over time, grouped by day. Spikes indicate active exfiltration events or new dump publications.</P>

        <H3>System Terminal</H3>
        <P>The terminal widget at the bottom of the dashboard shows live internal system events — Celery task completions, YARA scan results, Elasticsearch indexing status, and correlation updates. Logs rotate and keep the last 50 entries.</P>

        <Note type="warn">The terminal shows synthetic log events in demo mode. In production these are real worker events streamed via WebSocket.</Note>
      </>
    ),
  },
  {
    id: 'topology',
    label: 'Neural Topology',
    icon: Network,
    content: (
      <>
        <H2>Neural Topology Map</H2>
        <P>The Neural Topology is a force-directed graph that visualizes the relationships between monitored identities and their associated breach events.</P>

        <H3>Node Types</H3>
        <Table
          headers={['Color', 'Type', 'Meaning']}
          rows={[
            ['🔵 Blue', 'Identity', 'Monitored email/username/domain'],
            ['🟡 Yellow', 'Protected Identity', 'VIP asset with heightened monitoring'],
            ['🔴 Red', 'Critical Leak (≥80)', 'Severe breach event linked to an identity'],
            ['🟠 Orange', 'Moderate Leak', 'Breach event with severity 50–79'],
          ]}
        />

        <H3>Interaction</H3>
        <ul className="space-y-1 mb-3">
          <Li>Drag nodes to reorganize the graph layout</Li>
          <Li>Scroll to zoom in/out</Li>
          <Li>Hover over a node to see its label</Li>
          <Li>At high zoom levels (3x+), node labels become visible</Li>
          <Li>The graph auto-fits to the canvas on load and on data refresh</Li>
        </ul>

        <H3>Data Source</H3>
        <P>The graph is populated by {CODE('GET /identities/graph')} which queries the {CODE('identity_leaks')} association table directly via raw SQL for maximum performance.</P>
        <Note type="info">If no real data exists, the graph renders demo nodes so you can always inspect the visualization working correctly.</Note>
      </>
    ),
  },
  {
    id: 'identities',
    label: 'Master Identities',
    icon: Fingerprint,
    content: (
      <>
        <H2>Master Identities</H2>
        <P>Identities are the core intelligence objects in NASO. Each identity represents a monitored digital entity — an email address, username, phone number, or domain. NASO correlates breach events against these identities automatically via the Celery workers.</P>

        <H3>Identity Types</H3>
        <Table
          headers={['Type', 'Example']}
          rows={[
            ['person', 'john.doe (full name)'],
            ['email', 'john.doe@company.com'],
            ['username', 'jdoe92'],
            ['phone', '+1-555-123-4567'],
            ['domain', 'company.com'],
          ]}
        />

        <H3>Risk Score</H3>
        <P>The risk score (0–100) is computed by the AI triage worker based on the severity and volume of breach events linked to the identity. It updates automatically after each scan cycle.</P>
        <Table
          headers={['Score', 'Level', 'Color']}
          rows={[
            ['80–100', 'Critical', '🔴 Red'],
            ['50–79', 'High', '🟠 Orange'],
            ['0–49', 'Low / Normal', '🟢 Green'],
          ]}
        />

        <H3>Identity Protection</H3>
        <P>Marking an identity as <strong className="text-zinc-200">Protected (VIP)</strong> changes its Topology node to yellow and prioritizes its alerts in the notification feed. Use this for C-level executives, critical infrastructure accounts, or high-value targets.</P>

        <H3>Identity Merging</H3>
        <P>The {CODE('POST /identities/merge')} endpoint triggers the auto-merge algorithm which uses fuzzy matching to consolidate duplicate identities (e.g., the same person with multiple email variants) into a master/slave tree. Slave identities appear in the Insights dialog.</P>

        <H3>Identity Insights Dialog</H3>
        <P>Clicking <strong className="text-zinc-200">Insights</strong> on any identity opens a deep-analysis dialog showing:</P>
        <ul className="space-y-1 mb-3">
          <Li>All linked breach events, sorted by severity</Li>
          <Li>First and last seen timestamps</Li>
          <Li>Merged alias identities (slave tree)</Li>
          <Li>Risk score and protection status</Li>
        </ul>
      </>
    ),
  },
  {
    id: 'dark-recon',
    label: 'Dark Recon Probe',
    icon: Globe,
    content: (
      <>
        <H2>Dark Recon Probe</H2>
        <P>The Dark Recon module executes real-time OSINT queries against the dark web via the <strong className="text-zinc-200">Ahmia</strong> onion search engine index. All probes are logged in the Audit trail.</P>

        <H3>Query Syntax</H3>
        <P>Enter any keyword, email, domain, or threat actor name. The engine constructs an Ahmia search and returns matching .onion links with metadata.</P>
        <BLOCK lang="examples" code={`email@company.com
company.com credentials
"ransomware" "company name"
leaked database dump`} />

        <H3>Result Fields</H3>
        <Table
          headers={['Field', 'Description']}
          rows={[
            ['title', 'Page title of the .onion result'],
            ['url', 'Tor hidden service address (.onion)'],
            ['description', 'Excerpt / snippet from the indexed content'],
            ['score', 'Relevance score from Ahmia ranking'],
          ]}
        />

        <Note type="danger">Dark web reconnaissance results may contain links to illegal content. NASO only indexes metadata — it does not download or cache any content from .onion pages.</Note>

        <H3>Backend Implementation</H3>
        <P>Implemented in {CODE('DarkWebSearchService.search_onion_links(query)')} which makes HTTP requests to {CODE('https://ahmia.fi/search/')} and parses the HTML response. The Celery worker optionally takes screenshots of results via Selenium and stores them in MinIO.</P>
      </>
    ),
  },
  {
    id: 'audit',
    label: 'Audit & Compliance',
    icon: ScrollText,
    content: (
      <>
        <H2>Audit & Compliance</H2>
        <P>The Audit module provides a tamper-evident log of every significant action performed in NASO. Required for SOC 2, ISO 27001, and GDPR compliance workflows.</P>

        <H3>Logged Actions</H3>
        <Table
          headers={['Action', 'Trigger']}
          rows={[
            ['CREATE_IDENTITY', 'Adding a new monitored identity'],
            ['VIEW_IDENTITY_INSIGHTS', 'Opening the identity insights dialog'],
            ['DARK_WEB_RECON', 'Launching a dark web probe'],
            ['AI_DARK_WEB_PROBE', 'AI Co-Analyst dark web tool call'],
            ['AI_CHAT', 'Starting an AI investigation session'],
            ['AI_FLAG_LEAK', 'AI updating a leak status'],
            ['GENERATE_MASSIVE_DOSSIER', 'Exporting the full PDF dossier'],
            ['UPDATE_PROFILE', 'Operator profile update'],
            ['VIEW_LEAK_SCREENSHOT', 'Accessing a forensic screenshot'],
          ]}
        />

        <H3>Export CSV</H3>
        <P>Use the <strong className="text-zinc-200">Export CSV</strong> button on the Audit view to download the current log as a machine-readable CSV for SIEM ingestion or compliance reporting.</P>

        <H3>Retention</H3>
        <P>Audit logs are stored indefinitely in PostgreSQL with no automatic deletion. Implement your own archiving policy via database backup rotation.</P>

        <Note type="info">The audit table is tenant-isolated. Analysts can only see logs for their own tenant. Admins can see all tenants.</Note>
      </>
    ),
  },
  {
    id: 'ai-analyst',
    label: 'AI Co-Analyst',
    icon: Brain,
    content: (
      <>
        <H2>AI Co-Analyst</H2>
        <P>The AI Co-Analyst is a local LLM-powered forensic assistant integrated directly into NASO. It uses your existing AI endpoint (LM Studio, Ollama, or any OpenAI-compatible server) configured in {CODE('.env')} via {CODE('AI_ENDPOINT')} and {CODE('AI_MODEL')}.</P>

        <Note type="info">The AI runs entirely locally. No data leaves your infrastructure. The LLM only sees data that it explicitly requests via tool calls.</Note>

        <H3>Interface Layout</H3>
        <Table
          headers={['Panel', 'Description']}
          rows={[
            ['Left — Investigations', 'Create and manage investigation plans. Add tasks manually or let the AI create them.'],
            ['Center — Chat', 'Streaming conversation with the AI Co-Analyst.'],
            ['Right — Evidence', 'Structured results from tool calls, shown as collapsible cards.'],
          ]}
        />

        <H3>Tool Calls</H3>
        <P>When the AI needs real data, it calls one of these tools automatically — you will see a <strong className="text-zinc-200">tool badge</strong> appear in the chat before the AI responds:</P>
        <Table
          headers={['Tool', 'What it does']}
          rows={[
            ['search_identities', 'Query monitored identities by name or risk score'],
            ['get_leaks', 'Retrieve breach records filtered by source/severity/status'],
            ['dark_web_probe', 'Live dark web search via Ahmia'],
            ['get_identity_insights', 'Deep forensic analysis of a specific identity'],
            ['create_task', 'Adds a finding as a task to the active investigation plan'],
            ['flag_critical', 'Updates a leak status (reviewing, resolved, escalated)'],
          ]}
        />

        <H3>Investigation Plans</H3>
        <P>Create a plan before starting a complex investigation. The AI will automatically attach tasks to the active plan as it discovers findings. You can:</P>
        <ul className="space-y-1 mb-3">
          <Li>Create plans manually with a title and description</Li>
          <Li>Let the AI create tasks via {CODE('create_task')} tool calls</Li>
          <Li>Check off tasks as you verify each finding</Li>
          <Li>Mark plans as completed or archived</Li>
        </ul>

        <H3>Configuration</H3>
        <BLOCK lang=".env" code={`AI_ENDPOINT=http://host.docker.internal:1234/v1
AI_MODEL=google/gemma-4-E2B-it
AI_ENABLE_THINKING=true`} />

        <P>Compatible with LM Studio, Ollama ({CODE('http://localhost:11434/v1')}), and any OpenAI-compatible endpoint. Models with function/tool calling support work best (llama3.1, mistral-nemo, qwen2.5, gemma4).</P>

        <H3>Starter Prompts</H3>
        <BLOCK lang="examples" code={`"Find all critical breaches discovered this week"
"Investigate identity john@company.com"
"Search dark web for 'company credentials' and flag any critical hits"
"Create an investigation plan for a phishing campaign targeting HR"
"What identities have risk score above 80?"
"Show me all unreviewed leaks from Telegram"`} />
      </>
    ),
  },
  {
    id: 'api-reference',
    label: 'API Reference',
    icon: Code2,
    content: (
      <>
        <H2>API Reference</H2>
        <P>The NASO API is a RESTful JSON API secured with JWT Bearer tokens. Interactive docs available at {CODE('/api/docs')} (Swagger UI) and {CODE('/api/redoc')}.</P>

        <H3>Authentication</H3>
        <BLOCK lang="bash" code={`# Get a token
curl -X POST /auth/login \\
  -d 'username=you@example.com&password=secret' \\
  -H 'Content-Type: application/x-www-form-urlencoded'

# Use the token
curl /leaks/ -H 'Authorization: Bearer <token>'`} />

        <H3>Endpoints Summary</H3>
        <Table
          headers={['Method', 'Path', 'Description']}
          rows={[
            ['POST', '/auth/login', 'Get JWT token (form-data)'],
            ['GET', '/leaks/', 'List leaks (filter: source, status, min_severity)'],
            ['GET', '/leaks/recon/darkweb?q=', 'Dark web Tor probe'],
            ['GET', '/leaks/recon/telegram?channel=', 'Telegram public channel read'],
            ['GET', '/leaks/recon/shodan?ip=', 'Shodan IP vulnerability scan'],
            ['GET', '/leaks/export/dossier', 'Download full PDF dossier'],
            ['GET', '/leaks/{id}/intelligence', 'AI + YARA analysis for a leak'],
            ['PATCH', '/leaks/{id}/status', 'Update leak triage status'],
            ['GET', '/identities/', 'Search identities'],
            ['POST', '/identities/', 'Create new identity'],
            ['GET', '/identities/graph', 'Force-graph data'],
            ['GET', '/identities/{id}/insights', 'Deep identity analysis'],
            ['PATCH', '/identities/{id}/protect', 'Toggle VIP protection'],
            ['POST', '/identities/merge', 'Trigger auto-merge algorithm'],
            ['GET', '/system/status', 'Backend health check'],
            ['GET', '/system/audit?limit=&offset=', 'Audit log, paged (limit ≤ 200)'],
            ['GET', '/system/audit/verify', 'Verify the hash chain'],
            ['GET', '/system/health', 'Composite readiness across every backing service'],
            ['GET', '/users/me', 'The authenticated operator (how the SPA restores a session)'],
            ['PUT', '/users/me', 'Update operator profile'],
            ['POST', '/ai/chat', 'AI chat (SSE streaming)'],
            ['GET', '/ai/plans', 'List investigation plans'],
            ['POST', '/ai/plans', 'Create investigation plan'],
            ['PATCH', '/ai/plans/{id}', 'Update plan'],
            ['DELETE', '/ai/plans/{id}', 'Delete plan'],
            ['POST', '/ai/plans/{id}/tasks', 'Add task to plan'],
            ['PATCH', '/ai/plans/{id}/tasks/{tid}', 'Update task status'],
            ['GET', '/ai/health', 'AI engine health check'],
          ]}
        />

        <H3>Multi-Tenancy</H3>
        <P>All data is tenant-isolated. The tenant ID is embedded in the JWT token and enforced at the query level. Admins can see data across all tenants.</P>

        <Note type="warn">Never expose the NASO API directly to the internet without TLS termination and rate limiting.</Note>
      </>
    ),
  },
];

// ── DocsView component ────────────────────────────────────────────────────────

export default function DocsView() {
  const [search, setSearch] = useState('');
  const [activeSection, setActiveSection] = useState('getting-started');

  const filteredSections = useMemo(() => {
    if (!search.trim()) return SECTIONS;
    const q = search.toLowerCase();
    return SECTIONS.filter(s =>
      s.label.toLowerCase().includes(q) ||
      s.id.includes(q)
    );
  }, [search]);

  const currentSection = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0];

  return (
    <div className="flex h-full overflow-hidden">

      {/* Sidebar nav */}
      <div className="w-[220px] flex-shrink-0 border-r border-white/[0.06] flex flex-col">
        <div className="p-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={15} strokeWidth={1.5} className="text-zinc-400" />
            <span className="text-[13px] font-semibold text-white">Documentation</span>
          </div>
          <div className="relative">
            <Search size={12} strokeWidth={2} className="absolute left-3 top-2.5 text-zinc-600" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search docs..."
              className="w-full bg-white/[0.04] border border-white/[0.07] rounded-lg pl-8 pr-3 py-2 text-[12px] text-white placeholder-zinc-600 focus:outline-none focus:border-[#0A84FF]/40 transition-colors"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {filteredSections.map(section => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;
            return (
              <button
                key={section.id}
                onClick={() => { setActiveSection(section.id); setSearch(''); }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all mb-0.5 ${
                  isActive
                    ? 'bg-[#0A84FF]/15 text-[#0A84FF]'
                    : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04]'
                }`}
              >
                <Icon size={13} strokeWidth={1.5} />
                <span className="text-[12px] font-medium">{section.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-4 border-t border-white/[0.06]">
          <p className="text-[10px] text-zinc-700">NASO</p>
          <p className="text-[10px] text-zinc-700">v1.1.0 · API docs at /api/docs</p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">
          {currentSection.content}
        </div>
      </div>
    </div>
  );
}
