'use client';

import * as React from 'react';
import { Bookmark, FileText } from 'lucide-react';
import type { Citation } from '@nexusagent/contracts';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export interface CitationPillProps {
    citation?: Citation;
    filename?: string;
    startLine?: number | null;
    endLine?: number | null;
    headerPath?: string[];
    preview?: string;
    onClick?: (citation: { filename: string; startLine?: number | null; endLine?: number | null }) => void;
    className?: string;
}

export function CitationPill({
    citation,
    filename: propFilename,
    startLine: propStartLine,
    endLine: propEndLine,
    headerPath: propHeaderPath,
    preview: propPreview,
    onClick,
    className = ''
}: CitationPillProps) {
    const filename = citation?.filename || propFilename || 'Document';
    const startLine = citation?.startLine ?? propStartLine;
    const endLine = citation?.endLine ?? propEndLine;
    const headerPath = citation?.headerPath || propHeaderPath || [];
    const preview = citation?.preview || propPreview || '';

    const hasLineInfo = typeof startLine === 'number' && typeof endLine === 'number' && startLine > 0;
    const lineLabel = hasLineInfo ? (startLine === endLine ? `L${startLine}` : `L${startLine}-${endLine}`) : null;

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onClick) {
            onClick({ filename, startLine, endLine });
        }
    };

    return (
        <TooltipProvider delayDuration={150}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <button
                        type="button"
                        onClick={handleClick}
                        data-testid="citation-pill"
                        aria-label={`Citation reference: ${filename}${lineLabel ? ` lines ${lineLabel}` : ''}`}
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 my-0.5 rounded-md text-[11px] font-mono font-medium border transition-all cursor-pointer select-none bg-citation-bg text-citation-text border-citation-border hover:brightness-95 active:scale-95 ${className}`}
                    >
                        <FileText className="h-3 w-3 shrink-0 opacity-80" aria-hidden="true" />
                        <span className="truncate max-w-[160px] font-sans font-semibold tracking-tight">{filename}</span>
                        {lineLabel && <span className="text-[10px] px-1 py-0 rounded bg-primary/10 border border-primary/20 opacity-90">{lineLabel}</span>}
                    </button>
                </TooltipTrigger>
                <TooltipContent
                    side="top"
                    align="start"
                    className="max-w-xs sm:max-w-sm p-3 bg-card text-foreground border border-border rounded-xl shadow-xl space-y-1.5 text-xs"
                >
                    <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5">
                        <div className="flex items-center gap-1.5 text-primary font-bold truncate">
                            <Bookmark className="h-3.5 w-3.5 shrink-0" />
                            <span className="truncate">{filename}</span>
                        </div>
                        {lineLabel && (
                            <span className="font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground border border-border shrink-0">
                                {lineLabel}
                            </span>
                        )}
                    </div>

                    {headerPath.length > 0 && <p className="text-[10px] text-muted-foreground truncate font-medium">§ {headerPath.join(' › ')}</p>}

                    {preview ? (
                        <p className="text-[11px] text-foreground/90 font-serif italic line-clamp-3 bg-secondary/30 p-1.5 rounded border border-border/50">
                            &ldquo;{preview}&rdquo;
                        </p>
                    ) : (
                        <p className="text-[11px] text-muted-foreground italic">Retrieved from a knowledge base chunk.</p>
                    )}

                    <p className="pt-0.5 text-[10px] text-muted-foreground">Click to highlight this source in the Documents list.</p>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}
