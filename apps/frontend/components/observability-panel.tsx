'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Activity, CheckCircle2, ChevronRight, Cpu, GitFork, Loader2, RefreshCw, Terminal, Wrench, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Grounding, PlanStep, UsageEvent } from '@nexusagent/contracts';

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

export interface ToolCallItem {
    tool: string;
    args: any;
    durationMs?: number | null;
    resultsCount?: number | null;
}

export interface ObservabilityPanelProps {
    metrics?: TelemetryMetrics;
    logs: LogEntry[];
    currentNode?: string | null;
    nodeHistory?: string[];
    plan?: PlanStep[];
    grounding?: Grounding | null;
    usage?: UsageEvent[];
    sessionTokens?: { input: number; output: number; total: number };
    toolCalls?: ToolCallItem[];
    isStreaming?: boolean;
    className?: string;
    onClose?: () => void;
}

const NODE_LABELS: Record<string, string> = {
    router: 'Router',
    chat: 'Chat',
    retriever: 'Retriever',
    grounding: 'Grounding',
    answer: 'Answer',
    planner: 'Router',
    synthesizer: 'Answer'
};

const DEFAULT_NODES = ['router', 'retriever', 'grounding', 'answer'];

function formatMs(ms: number | null): string {
    if (ms === null) return '—';
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export function ObservabilityPanel({
    metrics,
    logs,
    currentNode,
    nodeHistory = [],
    plan = [],
    grounding = null,
    usage = [],
    sessionTokens,
    toolCalls = [],
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
        { label: 'Total latency', value: formatMs(metrics?.totalLatencyMs ?? null) }
    ];

    const runInputTokens = usage.reduce((sum, u) => sum + (u.inputTokens || 0), 0);
    const runOutputTokens = usage.reduce((sum, u) => sum + (u.outputTokens || 0), 0);
    const runTotalTokens = usage.reduce((sum, u) => sum + (u.totalTokens || 0), 0);
    const modelNames = Array.from(new Set(usage.map((u) => u.model).filter(Boolean))).join(', ');

    // Determine the ordered pipeline steps to display
    let displayNodes = nodeHistory.length > 0 ? [...nodeHistory] : [...DEFAULT_NODES];
    if (currentNode && !displayNodes.includes(currentNode)) {
        displayNodes.push(currentNode);
    }
    // Filter out synonyms
    displayNodes = displayNodes.filter((n, idx) => displayNodes.indexOf(n) === idx);

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
                        <span>Pipeline</span>
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
                    {displayNodes.map((nodeId, index) => {
                        const isCurrent = currentNode === nodeId;
                        const isPast = currentNode ? displayNodes.indexOf(currentNode) > index : nodeHistory.includes(nodeId);

                        const label = NODE_LABELS[nodeId] || nodeId;

                        return (
                            <React.Fragment key={nodeId}>
                                <div
                                    className={`flex flex-col items-center px-1.5 py-0.5 rounded text-center min-w-12 shrink-0 transition-all ${
                                        isCurrent
                                            ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                                            : isPast
                                              ? 'bg-primary/20 text-foreground font-medium'
                                              : 'bg-muted/40 text-muted-foreground'
                                    }`}
                                    aria-current={isCurrent ? 'step' : undefined}
                                >
                                    <span className="text-[10px] uppercase tracking-tight opacity-90">{isCurrent ? 'Active' : `S${index + 1}`}</span>
                                    <span className="text-xs leading-tight truncate">{label}</span>
                                </div>
                                {index < displayNodes.length - 1 && <ChevronRight className="h-3 w-3 text-muted-foreground/60 shrink-0" aria-hidden="true" />}
                            </React.Fragment>
                        );
                    })}
                </div>

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

            {/* Tokens Observability Card */}
            <Card className="p-2.5 shadow-2xs border-border bg-secondary/15" data-testid="tokens-card">
                <div className="flex items-center gap-1.5 text-xs font-heading font-semibold text-foreground mb-1.5">
                    <Cpu className="h-3.5 w-3.5 text-primary" />
                    <span>Tokens</span>
                </div>
                <dl className="grid grid-cols-3 gap-1.5 text-center">
                    <div className="rounded-md bg-card border border-border/70 px-1.5 py-1">
                        <dt className="text-[10px] text-muted-foreground uppercase tracking-wider">Input</dt>
                        <dd className="text-xs font-mono font-semibold text-foreground tabular-nums">{runInputTokens}</dd>
                    </div>
                    <div className="rounded-md bg-card border border-border/70 px-1.5 py-1">
                        <dt className="text-[10px] text-muted-foreground uppercase tracking-wider">Output</dt>
                        <dd className="text-xs font-mono font-semibold text-foreground tabular-nums">{runOutputTokens}</dd>
                    </div>
                    <div className="rounded-md bg-card border border-border/70 px-1.5 py-1">
                        <dt className="text-[10px] text-muted-foreground uppercase tracking-wider">Total</dt>
                        <dd className="text-xs font-mono font-semibold text-foreground tabular-nums">{runTotalTokens}</dd>
                    </div>
                </dl>
                <div className="mt-2 pt-1.5 border-t border-border flex flex-col gap-0.5 text-xs text-muted-foreground">
                    <div className="flex items-center justify-between">
                        <span>Session total:</span>
                        <span className="font-mono font-semibold text-foreground">{sessionTokens?.total ?? runTotalTokens}</span>
                    </div>
                    {modelNames && (
                        <div className="flex items-center justify-between text-[11px] truncate">
                            <span>Model:</span>
                            <span className="font-mono text-foreground truncate max-w-35" title={modelNames}>
                                {modelNames}
                            </span>
                        </div>
                    )}
                </div>
            </Card>

            {/* Tool Calls Card */}
            <Card className="p-2.5 shadow-2xs border-border bg-secondary/15" data-testid="tool-calls-card">
                <div className="flex items-center justify-between text-xs font-heading font-semibold text-foreground mb-1.5">
                    <div className="flex items-center gap-1.5">
                        <Wrench className="h-3.5 w-3.5 text-primary" />
                        <span>Tool Calls</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground font-mono">({toolCalls.length})</span>
                </div>
                {toolCalls.length === 0 ? (
                    <div className="text-xs text-muted-foreground text-center py-2">No tools called yet</div>
                ) : (
                    <div className="space-y-1.5">
                        {toolCalls.map((tc, idx) => {
                            const summary = tc.args?.queries
                                ? Array.isArray(tc.args.queries)
                                    ? tc.args.queries.join(', ')
                                    : String(tc.args.queries)
                                : tc.args?.query
                                  ? String(tc.args.query)
                                  : JSON.stringify(tc.args ?? {});
                            return (
                                <div key={idx} className="p-1.5 rounded-md bg-card border border-border/70 text-xs">
                                    <div className="flex items-center justify-between font-semibold">
                                        <span className="text-primary font-mono text-[11px]">{tc.tool}</span>
                                        <span className="text-muted-foreground text-[10px] font-mono">
                                            {tc.durationMs != null ? `${tc.durationMs}ms` : '—'}
                                        </span>
                                    </div>
                                    <p className="text-muted-foreground truncate text-[11px] mt-0.5" title={summary}>
                                        {summary}
                                    </p>
                                    {tc.resultsCount != null && (
                                        <div className="text-[10px] text-muted-foreground mt-0.5">
                                            Results: <span className="font-mono font-medium text-foreground">{tc.resultsCount}</span>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </Card>

            {/* Run Latency Metrics (client-measured) */}
            <Card className="p-2.5 shadow-2xs border-border bg-secondary/15" data-testid="run-metrics">
                <dl className="grid grid-cols-2 gap-1.5 text-center">
                    {metricTiles.map((tile) => (
                        <div key={tile.label} className="rounded-md bg-card border border-border/70 px-1.5 py-1">
                            <dt className="text-[10px] text-muted-foreground uppercase tracking-wider">{tile.label}</dt>
                            <dd className="text-xs font-mono font-semibold text-foreground tabular-nums">{tile.value}</dd>
                        </div>
                    ))}
                </dl>
            </Card>

            {/* Run log terminal */}
            <Card className="flex-1 flex flex-col shadow-2xs border-border bg-card overflow-hidden">
                <CardHeader className="p-2 pb-1.5 border-b border-border bg-secondary/30 flex flex-row items-center justify-between gap-1.5">
                    <div className="min-w-0 flex-1">
                        <CardTitle className="text-xs font-heading flex items-center gap-1.5">
                            <Terminal className="h-3 w-3 text-primary shrink-0" />
                            <span className="truncate">Run log</span>
                        </CardTitle>
                        <CardDescription className="text-xs text-muted-foreground truncate">Telemetry trace &amp; model routing</CardDescription>
                    </div>
                    <Badge variant={isStreaming ? 'soft' : 'outline'} className="text-xs px-1.5 py-0 shrink-0 whitespace-nowrap">
                        {isStreaming ? 'Streaming' : 'Idle'}
                    </Badge>
                </CardHeader>
                <CardContent className="p-2 flex-1 overflow-y-auto max-h-85 font-mono text-xs space-y-1.5 bg-secondary/40 text-foreground">
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
