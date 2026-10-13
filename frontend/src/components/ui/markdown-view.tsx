import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { CitationPill } from '@/components/ui/citation-card';
import { useToast } from '@/context/ToastContext';

interface MarkdownViewProps {
  content: string;
  onCitationClick?: (citationId: number) => void;
  className?: string;
}

export function MarkdownView({ content, onCitationClick, className }: MarkdownViewProps) {
  const { toast } = useToast();
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopyCode = (code: string, idx: number) => {
    navigator.clipboard.writeText(code);
    setCopiedIndex(idx);
    toast.success('Code copied to clipboard');
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // Robust line-level markdown renderer (citations, bold, inline code)
  const renderFormattedLine = (line: string, keyPrefix: string) => {
    // Check for citation tags like [1], [2]
    const parts = line.split(/(\[\d+\])/g);
    return (
      <span key={keyPrefix}>
        {parts.map((part, pIdx) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const id = parseInt(match[1], 10);
            return (
              <CitationPill
                key={`${keyPrefix}-cit-${pIdx}`}
                id={id}
                onClick={() => onCitationClick?.(id)}
              />
            );
          }

          // Handle bold text **text**
          const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
          return boldParts.map((bPart, bIdx) => {
            if (bPart.startsWith('**') && bPart.endsWith('**')) {
              return (
                <strong key={`${keyPrefix}-b-${bIdx}`} className="font-semibold text-gray-900 dark:text-white">
                  {bPart.slice(2, -2)}
                </strong>
              );
            }
            // Handle inline code `code`
            const codeParts = bPart.split(/(`[^`]+`)/g);
            return codeParts.map((cPart, cIdx) => {
              if (cPart.startsWith('`') && cPart.endsWith('`')) {
                return (
                  <code
                    key={`${keyPrefix}-c-${cIdx}`}
                    className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-[12.5px] font-mono text-indigo-700 dark:text-indigo-300 border border-slate-300/80 dark:border-slate-700"
                  >
                    {cPart.slice(1, -1)}
                  </code>
                );
              }
              return cPart;
            });
          });
        })}
      </span>
    );
  };

  // Split content into code blocks vs regular paragraphs/headings/lists
  const elements: React.ReactNode[] = [];
  const lines = content.split('\n');
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLang = '';
  let blockIndex = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (inCodeBlock) {
        // End code block
        const codeText = codeBuffer.join('\n');
        const currentIdx = blockIndex++;
        elements.push(
          <div
            key={`code-block-${currentIdx}`}
            className="my-3.5 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-900 shadow-sm"
          >
            <div className="flex items-center justify-between px-3.5 py-2 bg-slate-800/90 border-b border-slate-700/80 text-xs text-slate-300">
              <span className="font-mono text-[11px] uppercase tracking-wider font-medium text-slate-400">
                {codeLang || 'code'}
              </span>
              <button
                onClick={() => handleCopyCode(codeText, currentIdx)}
                className="flex items-center gap-1.5 hover:text-white transition-colors cursor-pointer text-xs font-medium text-slate-300"
                title="Copy code"
              >
                {copiedIndex === currentIdx ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5 text-slate-400" />
                    <span>Copy code</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-3.5 text-xs sm:text-[13px] font-mono overflow-x-auto text-slate-100 leading-relaxed">
              <code>{codeText}</code>
            </pre>
          </div>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        // Start code block
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Regular Markdown line formatting
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={`h1-${i}`} className="text-lg sm:text-xl font-bold mt-4 mb-2 text-gray-900 dark:text-white">
          {renderFormattedLine(line.slice(2), `h1-${i}`)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={`h2-${i}`} className="text-base sm:text-lg font-semibold mt-3.5 mb-1.5 text-gray-900 dark:text-white">
          {renderFormattedLine(line.slice(3), `h2-${i}`)}
        </h2>
      );
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={`h3-${i}`} className="text-sm sm:text-base font-semibold mt-2.5 mb-1 text-gray-800 dark:text-slate-100">
          {renderFormattedLine(line.slice(4), `h3-${i}`)}
        </h3>
      );
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <div key={`li-${i}`} className="flex items-start gap-2.5 my-1.5 text-[15px] sm:text-base text-gray-800 dark:text-slate-200 leading-[1.6]">
          <span className="text-blue-600 dark:text-blue-400 font-bold select-none mt-0.5">•</span>
          <div className="flex-1">{renderFormattedLine(line.slice(2), `li-${i}`)}</div>
        </div>
      );
    } else if (/^\d+\.\s+/.test(line)) {
      const match = line.match(/^(\d+)\.\s+(.*)$/);
      const num = match ? match[1] : '1';
      const rest = match ? match[2] : line;
      elements.push(
        <div key={`ol-${i}`} className="flex items-start gap-2.5 my-1.5 text-[15px] sm:text-base text-gray-800 dark:text-slate-200 leading-[1.6]">
          <span className="text-xs font-semibold text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/40 rounded-full h-5 w-5 flex items-center justify-center shrink-0 mt-0.5 select-none border border-blue-200 dark:border-blue-800/60">
            {num}
          </span>
          <div className="flex-1">{renderFormattedLine(rest, `ol-${i}`)}</div>
        </div>
      );
    } else if (line.trim() === '') {
      elements.push(<div key={`sp-${i}`} className="h-2" />);
    } else {
      elements.push(
        <p key={`p-${i}`} className="my-2 text-[15px] sm:text-base text-gray-800 dark:text-slate-200 leading-[1.6]">
          {renderFormattedLine(line, `p-${i}`)}
        </p>
      );
    }
  }

  return <div className={className}>{elements}</div>;
}
