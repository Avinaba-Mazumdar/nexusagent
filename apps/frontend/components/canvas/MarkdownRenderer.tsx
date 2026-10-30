'use client';

import * as React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Info, Terminal } from 'lucide-react';
import type { Citation } from '@nexusagent/contracts';
import { CitationPill } from './CitationPill';
import { MermaidViewer } from './MermaidViewer';
import { Button } from '@/components/ui/button';
import { TooltipProvider } from '@/components/ui/tooltip';

export interface MarkdownRendererProps {
    content: string;
    isStreaming?: boolean;
    citations?: Citation[];
    isDark?: boolean;
    onCitationClick?: (citation: Citation) => void;
    className?: string;
}

const CITATION_LABEL = /\[(S\d+)\]/g;
const ALERT_MARKER = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i;
const NUMBERED_HEADING = /^(\d+)\.\s+(.*)$/;
const SAFE_HREF = /^https?:\/\//i;

function CodeBlock({ language, code }: { language: string; code: string }) {
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
        <div className="my-3 rounded-xl border border-border bg-secondary/30 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border text-xs font-mono text-muted-foreground">
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
            <pre className="p-3 overflow-x-auto font-mono text-code text-foreground bg-card/60">
                <code>{code}</code>
            </pre>
        </div>
    );
}

/** Plain text of a React subtree (used to read headings and alert markers). */
function textOf(node: React.ReactNode): string {
    if (typeof node === 'string' || typeof node === 'number') return String(node);
    if (Array.isArray(node)) return node.map(textOf).join('');
    if (React.isValidElement<{ children?: React.ReactNode }>(node)) return textOf(node.props.children);
    return '';
}

export function MarkdownRenderer({ content, isStreaming = false, citations = [], isDark = false, onCitationClick, className = '' }: MarkdownRendererProps) {
    const citationByLabel = React.useMemo(() => new Map(citations.map((c) => [c.label, c])), [citations]);

    // An odd number of fences while streaming means the last code block is still being written.
    const unclosedFenceTail = React.useMemo(() => {
        if (!isStreaming) return null;
        const fences = content.match(/^```/gm)?.length ?? 0;
        if (fences % 2 === 0) return null;
        return content.slice(content.lastIndexOf('```') + 3);
    }, [content, isStreaming]);

    // Replace "[S1]" markers in text with citation pills; unknown labels stay as plain text.
    const withCitations = React.useCallback(
        (children: React.ReactNode): React.ReactNode =>
            React.Children.map(children, (child) => {
                if (typeof child !== 'string') return child;
                const parts: React.ReactNode[] = [];
                let last = 0;
                for (const match of child.matchAll(CITATION_LABEL)) {
                    const citation = citationByLabel.get(match[1]);
                    if (!citation) continue;
                    if (match.index > last) parts.push(child.slice(last, match.index));
                    parts.push(<CitationPill key={`${match.index}-${match[1]}`} citation={citation} onClick={onCitationClick} />);
                    last = match.index + match[0].length;
                }
                if (parts.length === 0) return child;
                if (last < child.length) parts.push(child.slice(last));
                return parts;
            }),
        [citationByLabel, onCitationClick]
    );

    const components = React.useMemo<Components>(() => {
        const heading = (Tag: 'h1' | 'h2' | 'h4', className: string) =>
            function Heading({ children }: { children?: React.ReactNode }) {
                return <Tag className={className}>{withCitations(children)}</Tag>;
            };

        return {
            h1: heading('h1', 'text-lg font-heading font-extrabold text-foreground mt-5 mb-2 tracking-tight'),
            h2: heading('h2', 'text-base font-heading font-bold text-foreground mt-5 mb-2 border-b border-border/80 pb-1.5 tracking-tight'),
            h3: ({ children }) => {
                const numbered = textOf(children).match(NUMBERED_HEADING);
                if (numbered) {
                    return (
                        <div className="mt-5 mb-2 flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded-md bg-primary/15 text-primary text-xs font-mono font-bold border border-primary/25">
                                {numbered[1]}
                            </span>
                            <h3 className="text-sm font-heading font-bold text-foreground tracking-wide uppercase">{numbered[2]}</h3>
                        </div>
                    );
                }
                return <h3 className="text-sm font-heading font-bold text-primary mt-4 mb-1.5 uppercase tracking-wider">{withCitations(children)}</h3>;
            },
            h4: heading('h4', 'text-sm font-heading font-semibold text-foreground mt-3 mb-1'),
            h5: heading('h4', 'text-sm font-heading font-semibold text-foreground mt-3 mb-1'),
            h6: heading('h4', 'text-sm font-heading font-semibold text-foreground mt-3 mb-1'),
            p: ({ children }) => <p className="text-sm leading-relaxed text-foreground/90 my-2">{withCitations(children)}</p>,
            ul: ({ children }) => <ul className="ml-5 list-disc space-y-1 my-2 text-sm leading-relaxed text-foreground/90">{children}</ul>,
            ol: ({ children, start }) => (
                <ol start={start} className="ml-5 list-decimal space-y-1 my-2 text-sm leading-relaxed text-foreground/90">
                    {children}
                </ol>
            ),
            li: ({ children }) => <li>{withCitations(children)}</li>,
            strong: ({ children }) => <strong className="font-bold text-foreground">{withCitations(children)}</strong>,
            em: ({ children }) => <em className="italic">{withCitations(children)}</em>,
            hr: () => <hr className="my-4 border-t border-border" />,
            a: ({ href, children }) =>
                href && SAFE_HREF.test(href) ? (
                    <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary font-medium underline underline-offset-2 hover:no-underline"
                    >
                        {children}
                    </a>
                ) : (
                    <span>{children}</span>
                ),
            table: ({ children }) => (
                <div className="my-3 overflow-x-auto rounded-xl border border-border bg-card/60 shadow-2xs">
                    <table className="w-full text-left text-sm border-collapse">{children}</table>
                </div>
            ),
            thead: ({ children }) => <thead className="bg-secondary/70 text-foreground font-semibold border-b border-border">{children}</thead>,
            tr: ({ children }) => <tr className="border-b border-border/60 last:border-0">{children}</tr>,
            th: ({ children, style }) => (
                <th style={style} className="px-3 py-2 font-semibold">
                    {withCitations(children)}
                </th>
            ),
            td: ({ children, style }) => (
                <td style={style} className="px-3 py-2 align-top text-foreground/90">
                    {withCitations(children)}
                </td>
            ),
            blockquote: ({ children }) => {
                const nodes = React.Children.toArray(children);
                const first = nodes.find((n) => React.isValidElement(n)) as React.ReactElement<{ children?: React.ReactNode }> | undefined;
                const firstChildren = React.Children.toArray(first?.props.children);
                const firstText = typeof firstChildren[0] === 'string' ? firstChildren[0] : '';
                const lead = firstText ? firstText.match(ALERT_MARKER) : null;
                const alertType = lead ? lead[1].toUpperCase() : null;

                let body: React.ReactNode = children;
                if (alertType && first && lead) {
                    const rest = [firstText.slice(lead[0].length), ...firstChildren.slice(1)].filter((c) => c !== '');
                    const stripped = React.cloneElement(first, undefined, ...rest);
                    body = nodes.map((n) => (n === first ? stripped : n));
                }

                const tone =
                    alertType === 'WARNING' || alertType === 'CAUTION'
                        ? 'border-warning bg-warning-bg'
                        : alertType === 'TIP'
                          ? 'border-success bg-success-bg'
                          : 'border-primary/80 bg-primary/10';
                return (
                    <div className={`my-3 p-3.5 rounded-xl border-l-4 text-sm leading-relaxed text-foreground ${tone}`}>
                        {alertType && (
                            <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-xs mb-1.5 text-primary">
                                <Info className="h-3.5 w-3.5" aria-hidden="true" />
                                <span>{alertType}</span>
                            </div>
                        )}
                        {body}
                    </div>
                );
            },
            pre: ({ children }) => <>{children}</>,
            code: ({ className: codeClass, children }) => {
                const language = /language-(\S+)/.exec(codeClass ?? '')?.[1]?.toLowerCase() ?? '';
                const code = React.Children.toArray(children)
                    .filter((c): c is string | number => typeof c === 'string' || typeof c === 'number')
                    .join('');
                const isBlock = Boolean(language) || code.endsWith('\n');
                if (!isBlock) {
                    return (
                        <code className="px-1 py-0.5 mx-0.5 rounded bg-secondary font-mono text-code text-primary font-semibold border border-border">
                            {children}
                        </code>
                    );
                }
                const trimmed = code.replace(/\n$/, '');
                if (language === 'mermaid') {
                    if (unclosedFenceTail !== null && unclosedFenceTail.includes(trimmed.slice(0, 40))) {
                        return (
                            <div className="my-2 p-3 rounded-xl border border-dashed border-primary/40 bg-secondary/20">
                                <div className="flex items-center gap-2 text-xs font-mono text-primary font-semibold mb-1">
                                    <span className="h-2 w-2 rounded-full bg-primary animate-ping" />
                                    Streaming architecture diagram syntax...
                                </div>
                                <pre className="text-code font-mono text-muted-foreground overflow-x-auto">
                                    <code>{trimmed}</code>
                                </pre>
                            </div>
                        );
                    }
                    return <MermaidViewer chart={trimmed} isDark={isDark} />;
                }
                return <CodeBlock language={language} code={trimmed} />;
            }
        };
    }, [withCitations, isDark, unclosedFenceTail]);

    return (
        <TooltipProvider delayDuration={150}>
            <div className={`markdown-content text-sm leading-relaxed ${className}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                    {content}
                </ReactMarkdown>
                {isStreaming && (
                    <span
                        data-testid="streaming-cursor"
                        className="inline-block w-1.5 h-3.5 ml-0.5 bg-primary animate-pulse rounded-xs align-baseline"
                        aria-hidden="true"
                    />
                )}

                {citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-border flex flex-wrap items-center gap-1.5 text-sm">
                        <span className="text-xs font-mono font-semibold text-muted-foreground mr-1">Sources:</span>
                        {citations.map((c) => (
                            <CitationPill key={`tray-${c.id}`} citation={c} onClick={onCitationClick} />
                        ))}
                    </div>
                )}
            </div>
        </TooltipProvider>
    );
}
