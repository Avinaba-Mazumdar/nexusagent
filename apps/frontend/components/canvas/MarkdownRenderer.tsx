'use client';

import * as React from 'react';
import { Check, Copy, Terminal, Info } from 'lucide-react';
import type { Citation } from '@nexusagent/contracts';
import { CitationPill } from './CitationPill';
import { MermaidViewer } from './MermaidViewer';
import { Button } from '@/components/ui/button';

export interface MarkdownRendererProps {
    content: string;
    isStreaming?: boolean;
    citations?: Citation[];
    isDark?: boolean;
    onCitationClick?: (citation: { filename: string; startLine?: number | null; endLine?: number | null }) => void;
    className?: string;
}

interface TableBlockProps {
    headers: string[];
    alignments: ('left' | 'center' | 'right')[];
    rows: string[][];
    renderCell: (cell: string) => React.ReactNode;
}

function TableBlock({ headers, alignments, rows, renderCell }: TableBlockProps) {
    return (
        <div className="my-3.5 overflow-x-auto rounded-xl border border-border bg-card/60 shadow-2xs">
            <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-secondary/70 text-foreground font-semibold border-b border-border">
                    <tr>
                        {headers.map((h, idx) => {
                            const align = alignments[idx] || 'left';
                            const alignClass = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';
                            return (
                                <th
                                    key={`th-${idx}`}
                                    className={`px-3.5 py-2.5 font-heading font-semibold text-[11px] tracking-tight border-r border-border/30 last:border-r-0 ${alignClass}`}
                                >
                                    {renderCell(h)}
                                </th>
                            );
                        })}
                    </tr>
                </thead>
                <tbody className="divide-y divide-border/40 text-foreground/90">
                    {rows.map((row, rIdx) => (
                        <tr key={`tr-${rIdx}`} className="hover:bg-secondary/20 transition-colors">
                            {row.map((cell, cIdx) => {
                                const align = alignments[cIdx] || 'left';
                                const alignClass = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';
                                return (
                                    <td
                                        key={`td-${rIdx}-${cIdx}`}
                                        className={`px-3.5 py-2.5 text-xs leading-relaxed border-r border-border/30 last:border-r-0 ${alignClass}`}
                                    >
                                        {renderCell(cell)}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

interface CodeBlockProps {
    language: string;
    code: string;
}

function CodeBlock({ language, code }: CodeBlockProps) {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Clipboard blocked
        }
    };

    return (
        <div className="my-2.5 rounded-xl border border-border bg-secondary/30 overflow-hidden text-xs">
            <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border text-[11px] font-mono text-muted-foreground">
                <div className="flex items-center gap-1.5">
                    <Terminal className="h-3 w-3 text-primary" />
                    <span>{language || 'text'}</span>
                </div>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    aria-label="Copy code block"
                    className="h-6 w-6 rounded text-muted-foreground hover:text-foreground"
                >
                    {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
                </Button>
            </div>
            <pre className="p-3 overflow-x-auto font-mono text-[11px] leading-relaxed text-foreground bg-card/60">
                <code>{code}</code>
            </pre>
        </div>
    );
}

export function MarkdownRenderer({ content, isStreaming = false, citations = [], isDark = false, onCitationClick, className = '' }: MarkdownRendererProps) {
    // Build citation lookup by filename for easy inline resolution
    const citationMap = React.useMemo(() => {
        const map = new Map<string, Citation>();
        for (const c of citations) {
            map.set(c.filename.toLowerCase(), c);
        }
        return map;
    }, [citations]);

    // Parse inline citation tags like [filename (Lines X-Y)] or [filename]
    const renderInlineWithCitations = (text: string): React.ReactNode => {
        const citationRegex = /\[([a-zA-Z0-9_\-.]+(?:\.md|\.txt|\.rfc)?)(?:\s*\((?:Lines?\s*)?(\d+)(?:-(\d+))?\))?\]/gi;
        const parts: React.ReactNode[] = [];
        let lastIndex = 0;
        let match: RegExpExecArray | null;

        while ((match = citationRegex.exec(text)) !== null) {
            const [fullMatch, filename, startLineStr, endLineStr] = match;
            const matchIndex = match.index;

            // Push preceding text formatted
            if (matchIndex > lastIndex) {
                parts.push(renderFormattedText(text.substring(lastIndex, matchIndex), `text-${lastIndex}`));
            }

            const startLine = startLineStr ? parseInt(startLineStr, 10) : undefined;
            const endLine = endLineStr ? parseInt(endLineStr, 10) : startLine;
            const matchedCitation = citationMap.get(filename.toLowerCase());

            parts.push(
                <CitationPill
                    key={`cite-${matchIndex}-${filename}`}
                    citation={matchedCitation}
                    filename={filename}
                    startLine={startLine}
                    endLine={endLine}
                    onClick={onCitationClick}
                />
            );

            lastIndex = matchIndex + fullMatch.length;
        }

        if (lastIndex < text.length) {
            parts.push(renderFormattedText(text.substring(lastIndex), `text-${lastIndex}`));
        }

        return parts.length > 0 ? parts : text;
    };

    // Formats bold, italic, and inline code spans
    const renderFormattedText = (raw: string, keyPrefix: string): React.ReactNode => {
        // Tokenize code spans `code`
        const codeParts = raw.split(/(`[^`]+`)/g);
        return codeParts.map((part, i) => {
            if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
                return (
                    <code
                        key={`${keyPrefix}-code-${i}`}
                        className="px-1 py-0.5 mx-0.5 rounded bg-secondary font-mono text-[11px] text-primary font-semibold border border-border"
                    >
                        {part.slice(1, -1)}
                    </code>
                );
            }

            // Bold **text**
            const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
            return (
                <React.Fragment key={`${keyPrefix}-bold-${i}`}>
                    {boldParts.map((bPart, j) => {
                        if (bPart.startsWith('**') && bPart.endsWith('**') && bPart.length >= 4) {
                            return (
                                <strong key={`${keyPrefix}-b-${j}`} className="font-bold text-foreground">
                                    {bPart.slice(2, -2)}
                                </strong>
                            );
                        }
                        return bPart;
                    })}
                </React.Fragment>
            );
        });
    };

    // Parse blocks: code fences, headings, lists, paragraphs
    const blocks = React.useMemo(() => {
        const result: React.ReactNode[] = [];
        const lines = content.split('\n');
        let inCodeBlock = false;
        let codeLanguage = '';
        let codeBuffer: string[] = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // Code fence toggle
            if (line.startsWith('```')) {
                if (inCodeBlock) {
                    // Close code block
                    const fullCode = codeBuffer.join('\n');
                    if (codeLanguage === 'mermaid') {
                        result.push(<MermaidViewer key={`mermaid-${i}`} chart={fullCode} isDark={isDark} />);
                    } else {
                        result.push(<CodeBlock key={`code-${i}`} language={codeLanguage} code={fullCode} />);
                    }
                    inCodeBlock = false;
                    codeLanguage = '';
                    codeBuffer = [];
                } else {
                    inCodeBlock = true;
                    codeLanguage = line.slice(3).trim().toLowerCase();
                    codeBuffer = [];
                }
                continue;
            }

            if (inCodeBlock) {
                codeBuffer.push(line);
                continue;
            }

            // Horizontal Rule
            if (line.trim() === '---' || line.trim() === '***') {
                result.push(<hr key={`hr-${i}`} className="my-4 border-t border-border" />);
                continue;
            }

            // Headings
            if (line.startsWith('# ')) {
                result.push(
                    <h1 key={`h1-${i}`} className="text-base font-heading font-extrabold text-foreground mt-4 mb-2 tracking-tight">
                        {renderInlineWithCitations(line.slice(2))}
                    </h1>
                );
                continue;
            }
            if (line.startsWith('## ')) {
                result.push(
                    <h2
                        key={`h2-${i}`}
                        className="text-sm font-heading font-bold text-foreground mt-4 mb-2 border-b border-border/80 pb-1.5 tracking-tight flex items-center gap-2"
                    >
                        {renderInlineWithCitations(line.slice(3))}
                    </h2>
                );
                continue;
            }
            if (line.startsWith('### ')) {
                const headingText = line.slice(4).trim();
                const catMatch = headingText.match(/^(\d+)\.\s*(.*)/);
                if (catMatch) {
                    result.push(
                        <div key={`cat-h-${i}`} className="mt-4.5 mb-2 flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded-md bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/25">
                                {catMatch[1]}
                            </span>
                            <h3 className="text-xs font-heading font-bold text-foreground tracking-wide uppercase">{renderInlineWithCitations(catMatch[2])}</h3>
                        </div>
                    );
                } else {
                    result.push(
                        <h3 key={`h3-${i}`} className="text-xs font-heading font-bold text-primary mt-3.5 mb-1.5 uppercase tracking-wider">
                            {renderInlineWithCitations(headingText)}
                        </h3>
                    );
                }
                continue;
            }

            // Table detection
            const isTableLine = (l: string) => {
                const trimmed = l.trim();
                return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|');
            };
            const isDelimiterRow = (l: string) => {
                const trimmed = l.trim();
                if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return false;
                const cells = trimmed
                    .slice(1, -1)
                    .split('|')
                    .map((c) => c.trim());
                return cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c));
            };
            const parseRowCells = (rowLine: string) => {
                return rowLine
                    .trim()
                    .slice(1, -1)
                    .split(/(?<!\\)\|/)
                    .map((c) => c.replace(/\\\|/g, '|').trim());
            };

            if (isTableLine(line) && i + 1 < lines.length && isDelimiterRow(lines[i + 1])) {
                const headerCells = parseRowCells(line);
                const delimiterCells = parseRowCells(lines[i + 1]);
                const alignments = delimiterCells.map((c) => {
                    const starts = c.startsWith(':');
                    const ends = c.endsWith(':');
                    if (starts && ends) return 'center' as const;
                    if (ends) return 'right' as const;
                    return 'left' as const;
                });

                const bodyRows: string[][] = [];
                i += 2;
                while (i < lines.length && isTableLine(lines[i])) {
                    bodyRows.push(parseRowCells(lines[i]));
                    i++;
                }
                i--; // Adjust for loop increment

                result.push(
                    <TableBlock
                        key={`table-${i}`}
                        headers={headerCells}
                        alignments={alignments}
                        rows={bodyRows}
                        renderCell={(cell) => renderInlineWithCitations(cell)}
                    />
                );
                continue;
            }

            // Blockquotes & Callouts
            if (line.trim().startsWith('>')) {
                const quoteLines: string[] = [];
                while (i < lines.length && lines[i].trim().startsWith('>')) {
                    quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
                    i++;
                }
                i--; // Adjust for loop increment

                const firstLine = quoteLines[0] || '';
                const alertMatch = firstLine.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
                const alertType = alertMatch ? alertMatch[1].toUpperCase() : null;
                const displayLines = alertMatch
                    ? [firstLine.replace(/^\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i, ''), ...quoteLines.slice(1)].filter((l) => l.length > 0)
                    : quoteLines;

                result.push(
                    <div
                        key={`quote-${i}`}
                        className={`my-3 p-3.5 rounded-xl border-l-4 text-xs leading-relaxed ${
                            alertType === 'WARNING' || alertType === 'CAUTION'
                                ? 'border-amber-500/80 bg-amber-500/10 text-foreground'
                                : alertType === 'TIP'
                                  ? 'border-emerald-500/80 bg-emerald-500/10 text-foreground'
                                  : 'border-primary/80 bg-primary/10 text-foreground'
                        }`}
                    >
                        {alertType && (
                            <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-[11px] mb-1.5 text-primary">
                                <Info className="h-3.5 w-3.5" />
                                <span>{alertType}</span>
                            </div>
                        )}
                        {displayLines.map((ql, qIdx) => (
                            <p key={`qp-${qIdx}`} className="my-1 leading-relaxed text-foreground/90">
                                {renderInlineWithCitations(ql)}
                            </p>
                        ))}
                    </div>
                );
                continue;
            }

            // Unordered list item
            if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
                const itemText = line.trim().slice(2);
                result.push(
                    <li key={`li-${i}`} className="ml-4 list-disc text-xs leading-relaxed text-foreground/90 my-1">
                        {renderInlineWithCitations(itemText)}
                    </li>
                );
                continue;
            }

            // Numbered list item & Category header fallback
            const numMatch = line.trim().match(/^(\d+)\.\s+(.*)/);
            if (numMatch) {
                const text = numMatch[2].trim();
                if (text.length > 3 && text === text.toUpperCase() && !text.includes(':') && !text.endsWith('.')) {
                    result.push(
                        <div key={`cat-h-${i}`} className="mt-4.5 mb-2 flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded-md bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/25">
                                {numMatch[1]}
                            </span>
                            <h3 className="text-xs font-heading font-bold text-foreground tracking-wide uppercase">{renderInlineWithCitations(text)}</h3>
                        </div>
                    );
                    continue;
                }
                result.push(
                    <li key={`ol-${i}`} className="ml-4 list-decimal text-xs leading-relaxed text-foreground/90 my-1">
                        {renderInlineWithCitations(numMatch[2])}
                    </li>
                );
                continue;
            }

            // Empty line
            if (!line.trim()) {
                result.push(<div key={`empty-${i}`} className="h-2" />);
                continue;
            }

            // Standard paragraph
            result.push(
                <p key={`p-${i}`} className="text-xs leading-relaxed text-foreground/90 my-1.5">
                    {renderInlineWithCitations(line)}
                </p>
            );
        }

        // Handle streaming unclosed code block
        if (inCodeBlock && codeBuffer.length > 0) {
            const unclosedCode = codeBuffer.join('\n');
            if (codeLanguage === 'mermaid') {
                result.push(
                    <div key="streaming-mermaid" className="my-2 p-3 rounded-xl border border-dashed border-primary/40 bg-secondary/20">
                        <div className="flex items-center gap-2 text-xs font-mono text-primary font-semibold mb-1">
                            <span className="h-2 w-2 rounded-full bg-primary animate-ping" />
                            Streaming architecture diagram syntax...
                        </div>
                        <pre className="text-[10px] font-mono text-muted-foreground overflow-x-auto">
                            <code>{unclosedCode}</code>
                        </pre>
                    </div>
                );
            } else {
                result.push(<CodeBlock key="streaming-code" language={codeLanguage} code={unclosedCode} />);
            }
        }

        return result;
    }, [content, isDark, renderInlineWithCitations]);

    return (
        <div className={`markdown-content space-y-2.5 text-xs leading-relaxed ${className}`}>
            {blocks}
            {isStreaming && (
                <span
                    data-testid="streaming-cursor"
                    className="inline-block w-1.5 h-3 ml-0.5 bg-primary animate-pulse rounded-xs align-baseline"
                    aria-hidden="true"
                />
            )}

            {/* Grounding references section if citations exist */}
            {citations.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-border flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="text-[11px] font-mono font-semibold text-muted-foreground mr-1">Grounding Citations:</span>
                    {citations.map((c, idx) => (
                        <CitationPill key={`tray-${c.id || idx}`} citation={c} onClick={onCitationClick} />
                    ))}
                </div>
            )}
        </div>
    );
}
