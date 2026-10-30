'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Activity, CheckCircle2, ChevronRight, GitFork, Loader2, RefreshCw, Terminal, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Grounding, PlanStep } from '@nexusagent/contracts';

export interface LogEntry {
    id: string;
    timestamp: string;
    stage: 'ROUTER' | 'RAG' | 'INFERENCE' | 'STREAM';
    message: string;
}

/** Client-measured timings for the most recent run; null until observed. */
export interface TelemetryMetrics {
    firstTokenMs: number | null;
    totalLatencyMs: number | null;
}

export interface ObservabilityPanelProps {
    metrics?: TelemetryMetrics;
    logs: LogEntry[];
    currentNode?: string | null;
    plan?: PlanStep[];
    grounding?: Grounding | null;
    isStreaming?: boolean;
    className?: string;
    onClose?: () => void;
}

const DAG_NODES = [
    { id: 'planner', label: 'Planner', step: 1 },
    { id: 'retriever', label: 'Retriever', step: 2 },
    { id: 'grounding', label: 'Grounding', step: 3 },
    { id: 'synthesizer', label: 'Synthesizer', step: 4 }
];

function formatMs(ms: number | null): string {
    if (ms === null) return '—';
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export function ObservabilityPanel({
    metrics,
    logs,
    currentNode,
    plan = [],
    grounding = null,
    isStreaming = false,
    className,
    onClose
}: ObservabilityPanelProps) {
    const logsEndRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (typeof logsEndRef.current?.scrollIntoView === 'function') {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    const metricTiles = [
        { label: 'First token', value: formatMs(metrics?.firstTokenMs ?? null) },
        { label: 'Total', value: formatMs(metrics?.totalLatencyMs ?? null) }
    ];

    return (
        <aside
            aria-label="Agent Telemetry & Observability"
            className={cn('w-full xl:w-72 bg-card border-l border-border flex flex-col shrink-0 overflow-y-auto p-2.5 space-y-2.5', className)}
        >
            {/* Header with Collapse Action */}
            <div className="flex items-center justify-between pb-2 border-b border-border">
                <h2 className="flex items-center gap-1.5 text-xs font-heading font-bold text-foreground">
                    <Activity className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                    <span>Real-time Observability</span>
                </h2>
                {onClose && (
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        onClick={onClose}
                        title="Collapse Observability Panel"
                        aria-label="Collapse Observability Panel"
                        className="h-6 w-6 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md cursor-pointer -mr-1"
                    >
                        <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                )}
            </div>

            {/* Reactive DAG Execution Pipeline Tracker */}
            <Card className="p-2.5 shadow-2xs border-border bg-secondary/15">
                <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5 text-xs font-heading font-semibold text-foreground">
                        <GitFork className="h-3.5 w-3.5 text-primary" />
                        <span>LangGraph DAG Pipeline</span>
                    </div>
                    {isStreaming && (
                        <Badge variant="soft" className="text-xs gap-1 px-1.5 py-0 bg-primary/20 text-primary">
                            <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden="true" />
                            Live
                        </Badge>
                    )}
                </div>

                {/* DAG Node Progress Bar */}
                <div className="flex items-center justify-between gap-1 py-1 overflow-x-auto">
                    {DAG_NODES.map((node, index) => {
                        const isCurrent = currentNode === node.id;
                        const isPast = currentNode && DAG_NODES.findIndex((n) => n.id === currentNode) > index;

                        return (
                            <React.Fragment key={node.id}>
                                <div
                                    className={`flex flex-col items-center px-1 py-0.5 rounded text-center min-w-[52px] shrink-0 transition-all ${
                                        isCurrent
                                            ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                                            : isPast
                                              ? 'bg-primary/20 text-foreground font-medium'
                                              : 'bg-muted/40 text-muted-foreground'
                                    }`}
                                    aria-current={isCurrent ? 'step' : undefined}
                                >
                                    <span className="text-xs uppercase tracking-tight opacity-90">{isCurrent ? 'Active' : `S${node.step}`}</span>
                                    <span className="text-xs leading-tight truncate">{node.label}</span>
                                </div>
                                {index < DAG_NODES.length - 1 && <ChevronRight className="h-3 w-3 text-muted-foreground/60 shrink-0" aria-hidden="true" />}
                            </React.Fragment>
                        );
                    })}
                </div>

                {/* Run Metrics (client-measured) */}
                <dl className="mt-2 pt-1.5 border-t border-border grid grid-cols-2 gap-1.5" data-testid="run-metrics">
                    {metricTiles.map((tile) => (
                        <div key={tile.label} className="rounded-md bg-card border border-border/70 px-1.5 py-1 text-center">
                            <dt className="text-xs text-muted-foreground">{tile.label}</dt>
                            <dd className="text-xs font-mono font-semibold text-foreground tabular-nums">{tile.value}</dd>
                        </div>
                    ))}
                </dl>

                {/* Grounding: did retrieval find usable sources? */}
                {grounding && (
                    <div className="mt-2 pt-1.5 border-t border-border flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1">
                            <RefreshCw className="h-3 w-3 text-primary" aria-hidden="true" />
                            Sources:
                        </span>
                        <Badge
                            variant="outline"
                            className={`text-xs font-bold ${
                                grounding === 'grounded'
                                    ? 'border-success-border text-success bg-success-bg'
                                    : 'border-warning-border text-warning bg-warning-bg'
                            }`}
                        >
                            {grounding === 'grounded' ? 'Grounded' : grounding === 'weak' ? 'Weak match' : 'None found'}
                        </Badge>
                    </div>
                )}

                {/* Live Plan Execution Steps */}
                {plan.length > 0 && (
                    <div className="mt-1.5 pt-1.5 border-t border-border space-y-1">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Active Plan Steps ({plan.filter((s) => s.status === 'completed').length}/{plan.length})
                        </div>
                        {plan.map((step) => (
                            <div key={step.stepNumber} className="flex items-start gap-1.5 text-xs text-foreground/90 leading-snug">
                                {step.status === 'completed' ? (
                                    <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0 mt-px" aria-label="Completed" />
                                ) : step.status === 'failed' ? (
                                    <XCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-px" aria-label="Failed" />
                                ) : step.status === 'in_progress' ? (
                                    <Loader2 className="h-3.5 w-3.5 text-primary animate-spin shrink-0 mt-px" aria-label="In progress" />
                                ) : (
                                    <span
                                        className="h-3.5 w-3.5 rounded-full border border-muted-foreground/50 flex items-center justify-center text-xs text-muted-foreground shrink-0 mt-px"
                                        aria-label="Pending"
                                    >
                                        {step.stepNumber}
                                    </span>
                                )}
                                <span className={step.status === 'completed' ? 'text-muted-foreground' : step.status === 'failed' ? 'text-destructive' : ''}>
                                    {step.description}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </Card>

            {/* Wire Logs Streaming Terminal */}
            <Card className="flex-1 flex flex-col shadow-2xs border-border bg-card overflow-hidden">
                <CardHeader className="p-2 pb-1.5 border-b border-border bg-secondary/30 flex flex-row items-center justify-between gap-1.5">
                    <div className="min-w-0 flex-1">
                        <CardTitle className="text-xs font-heading flex items-center gap-1.5">
                            <Terminal className="h-3 w-3 text-primary shrink-0" />
                            <span className="truncate">Execution Wire Logs</span>
                        </CardTitle>
                        <CardDescription className="text-xs text-muted-foreground truncate">Telemetry trace &amp; model routing</CardDescription>
                    </div>
                    <Badge variant={isStreaming ? 'soft' : 'outline'} className="text-xs px-1.5 py-0 shrink-0 whitespace-nowrap">
                        {isStreaming ? 'Streaming' : 'Idle'}
                    </Badge>
                </CardHeader>
                <CardContent className="p-2 flex-1 overflow-y-auto max-h-[340px] font-mono text-xs space-y-1.5 bg-secondary/40 text-foreground">
                    {logs.length === 0 ? (
                        <div className="text-muted-foreground py-4 text-center text-xs">Awaiting agent trigger. Stream logs will appear here.</div>
                    ) : (
                        logs.map((log) => (
                            <div key={log.id} className="leading-snug border-b border-border pb-1 last:border-0">
                                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <span suppressHydrationWarning>{log.timestamp}</span>
                                    <span
                                        className={`px-1 rounded text-xs font-bold ${
                                            log.stage === 'ROUTER'
                                                ? 'bg-primary/10 text-primary border border-primary/20'
                                                : log.stage === 'RAG'
                                                  ? 'bg-accent text-accent-foreground border border-border'
                                                  : 'bg-warning-bg text-warning border border-warning-border'
                                        }`}
                                    >
                                        [{log.stage}]
                                    </span>
                                </div>
                                <p className="text-foreground/90 mt-0.5 break-words text-xs">{log.message}</p>
                            </div>
                        ))
                    )}
                    <div ref={logsEndRef} />
                </CardContent>
            </Card>
        </aside>
    );
}
