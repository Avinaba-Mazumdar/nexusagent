'use client';

import * as React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import type { Citation, DocumentChunkResponse } from '@nexusagent/contracts';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api-client';

export interface SourceDialogProps {
    citation: Citation | null;
    onClose: () => void;
}

/** Server answers for a chunk or document that was re-seeded or deleted after the citation was saved. */
const GONE_MESSAGES = new Set(['Chunk not found', 'Document not found']);

type LoadState = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; chunk: DocumentChunkResponse };

/** Shows the full passage a citation points at, without leaving the answer. */
export function SourceDialog({ citation, onClose }: SourceDialogProps) {
    const [state, setState] = React.useState<LoadState>({ status: 'loading' });

    React.useEffect(() => {
        if (!citation) return;
        let cancelled = false;
        setState({ status: 'loading' });
        apiClient<DocumentChunkResponse>(`/api/documents/${citation.documentId}/chunks/${citation.chunkId}`)
            .then((chunk) => {
                if (!cancelled) setState({ status: 'ready', chunk });
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                const message = err instanceof Error ? err.message : '';
                setState({
                    status: 'error',
                    message: GONE_MESSAGES.has(message) ? 'This passage is no longer available.' : message || 'Could not load the source.'
                });
            });
        return () => {
            cancelled = true;
        };
    }, [citation]);

    const lines =
        citation && typeof citation.startLine === 'number' && citation.startLine > 0
            ? citation.startLine === citation.endLine
                ? `line ${citation.startLine}`
                : `lines ${citation.startLine}-${citation.endLine}`
            : null;

    return (
        <Dialog open={citation !== null} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col gap-3">
                <DialogHeader>
                    <DialogTitle className="text-base font-mono break-all">{citation?.filename}</DialogTitle>
                    <DialogDescription>
                        {citation?.label}
                        {lines ? ` · ${lines}` : ''}
                        {citation && citation.headerPath.length > 0 ? ` · ${citation.headerPath.join(' › ')}` : ''}
                    </DialogDescription>
                </DialogHeader>

                <div className="overflow-y-auto rounded-xl border border-border bg-secondary/30 p-3 min-h-24">
                    {state.status === 'loading' && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                            <span>Loading source…</span>
                        </div>
                    )}
                    {state.status === 'error' && (
                        <p className="flex items-start gap-1.5 text-sm text-destructive" role="alert">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
                            <span>{state.message}</span>
                        </p>
                    )}
                    {state.status === 'ready' && (
                        <pre data-testid="source-passage" className="whitespace-pre-wrap break-words font-mono text-code text-foreground">
                            {state.chunk.content}
                        </pre>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
