import React, { Suspense, lazy, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from '@/store/useToastStore';

// The highlighter pulls in Prism + language grammars — lazy-load so it only
// arrives in a separate chunk when the AI actually emits a code block.
const CodeBlockInner = lazy(() => import('./CodeBlockInner'));

// Fallback preserves the raw source while the highlighter chunk arrives.
function RawPre({ children }) {
  return (
    <pre className="text-[12px] font-mono leading-[1.55] text-zinc-300 whitespace-pre-wrap break-words">
      {String(children).replace(/\n$/, '')}
    </pre>
  );
}

/**
 * ReactMarkdown `code` renderer. Inline code stays lightweight; fenced blocks
 * get a header with language tag + copy button and the lazy Prism highlighter.
 */
export default function CodeBlock({ inline, className = '', children, ...props }) {
  const [copied, setCopied] = useState(false);

  if (inline) {
    return (
      <code
        className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.05] text-[11.5px] font-mono text-[#0A84FF]"
        {...props}
      >
        {children}
      </code>
    );
  }

  const match = /language-([\w-]+)/.exec(className);
  const language = match ? match[1].toLowerCase() : null;
  const source = String(children).replace(/\n$/, '');

  const copy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      toast.success('Code copied');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Copy failed');
    }
  };

  return (
    <div className="my-2 rounded-xl border border-white/[0.06] bg-black/40 overflow-hidden not-prose">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.04] bg-black/30">
        <span className="text-[10px] font-mono font-medium text-zinc-500 uppercase tracking-wider">
          {language || 'text'}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label="Copy code"
          className="flex items-center gap-1 h-5 px-2 rounded text-[10px] text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          {copied ? <Check size={10} className="text-[#32D74B]" /> : <Copy size={10} strokeWidth={1.8} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="px-4 py-3 overflow-x-auto scrollbar-thin">
        <Suspense fallback={<RawPre>{source}</RawPre>}>
          <CodeBlockInner language={language}>{source}</CodeBlockInner>
        </Suspense>
      </div>
    </div>
  );
}
