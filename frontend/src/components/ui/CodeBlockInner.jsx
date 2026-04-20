import React from 'react';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Register only the languages analysts actually paste into NASO. Keeping this
// list tight is the whole reason we use prism-light: each language import
// adds ~5-15 kB to the lazy chunk.
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import python     from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import bash       from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import json       from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import yaml       from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';
import sql        from 'react-syntax-highlighter/dist/esm/languages/prism/sql';
import go         from 'react-syntax-highlighter/dist/esm/languages/prism/go';
import rust       from 'react-syntax-highlighter/dist/esm/languages/prism/rust';
import http       from 'react-syntax-highlighter/dist/esm/languages/prism/http';
import markup     from 'react-syntax-highlighter/dist/esm/languages/prism/markup';

SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('js',         javascript);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('ts',         typescript);
SyntaxHighlighter.registerLanguage('python',     python);
SyntaxHighlighter.registerLanguage('py',         python);
SyntaxHighlighter.registerLanguage('bash',       bash);
SyntaxHighlighter.registerLanguage('sh',         bash);
SyntaxHighlighter.registerLanguage('shell',      bash);
SyntaxHighlighter.registerLanguage('json',       json);
SyntaxHighlighter.registerLanguage('yaml',       yaml);
SyntaxHighlighter.registerLanguage('yml',        yaml);
SyntaxHighlighter.registerLanguage('sql',        sql);
SyntaxHighlighter.registerLanguage('go',         go);
SyntaxHighlighter.registerLanguage('rust',       rust);
SyntaxHighlighter.registerLanguage('rs',         rust);
SyntaxHighlighter.registerLanguage('http',       http);
SyntaxHighlighter.registerLanguage('html',       markup);
SyntaxHighlighter.registerLanguage('xml',        markup);

// Soften oneDark's background to match NASO panels.
const theme = {
  ...oneDark,
  'pre[class*="language-"]': {
    ...oneDark['pre[class*="language-"]'],
    background: 'transparent',
    margin: 0,
    padding: 0,
    fontSize: '12px',
    lineHeight: 1.55,
  },
  'code[class*="language-"]': {
    ...oneDark['code[class*="language-"]'],
    background: 'transparent',
    fontSize: '12px',
    fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
  },
};

export default function CodeBlockInner({ language, children }) {
  return (
    <SyntaxHighlighter
      language={language || 'text'}
      style={theme}
      PreTag="div"
      codeTagProps={{ style: { fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace' } }}
    >
      {String(children).replace(/\n$/, '')}
    </SyntaxHighlighter>
  );
}
