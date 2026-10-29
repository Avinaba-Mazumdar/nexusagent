'use client';

import * as React from 'react';
import type { AgentInvokeResponse, Citation, PlanStep } from '@nexusagent/contracts';
import type { LogEntry, TelemetryMetrics } from '@/components/observability-panel';

import { API_BASE } from '@/lib/api-client';

export interface UseAgentStreamOptions {
    onLog?: (entry: LogEntry) => void;
    onMetricUpdate?: (updater: (prev: TelemetryMetrics) => TelemetryMetrics) => void;
}

export interface StreamParams {
    query: string;
    documentId?: string | null;
    sessionId?: string | null;
    token?: string | null;
    /** Optional BYOK provider credential; bypasses the server-side free-tier token bucket. */
    byokKey?: string | null;
}

/** Raised for HTTP failures and server-side stream errors so callers can render them. */
export class AgentStreamError extends Error {
    constructor(
        message: string,
        readonly status?: number
    ) {
        super(message);
        this.name = 'AgentStreamError';
    }
}

function describeHttpError(status: number, body: string): string {
    let detail = body;
    try {
        const parsed = JSON.parse(body);
        if (typeof parsed?.detail === 'string') detail = parsed.detail;
    } catch {
        // Plain-text body
    }
    if (status === 429) return 'Query quota exhausted. It replenishes hourly.';
    if (status === 401) return 'Your session has expired. Please sign in again.';
    return `Server returned status ${status}: ${detail}`;
}

export function useAgentStream(options?: UseAgentStreamOptions) {
    const [isStreaming, setIsStreaming] = React.useState(false);
    const [streamError, setStreamError] = React.useState<string | null>(null);
    const [plan, setPlan] = React.useState<PlanStep[]>([]);
    const [currentNode, setCurrentNode] = React.useState<string | null>(null);
    const [citations, setCitations] = React.useState<Citation[]>([]);
    const [streamedResponse, setStreamedResponse] = React.useState('');
    const [mermaidDiagrams, setMermaidDiagrams] = React.useState<string[]>([]);
    const [reflectionScore, setReflectionScore] = React.useState(0);
    const [isGrounded, setIsGrounded] = React.useState(false);
    const [isComplete, setIsComplete] = React.useState(false);
    const [sessionId, setSessionId] = React.useState<string | null>(null);

    const abortControllerRef = React.useRef<AbortController | null>(null);

    const cancelStream = React.useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsStreaming(false);
    }, []);

    const startStream = React.useCallback(
        async (params: StreamParams): Promise<AgentInvokeResponse | null> => {
            const { query, documentId, sessionId: existingSessionId, token, byokKey } = params;

            cancelStream();

            setIsStreaming(true);
            setStreamError(null);
            setPlan([]);
            setCurrentNode(null);
            setCitations([]);
            setStreamedResponse('');
            setMermaidDiagrams([]);
            setReflectionScore(0);
            setIsGrounded(false);
            setIsComplete(false);

            const controller = new AbortController();
            abortControllerRef.current = controller;
            const startTime = performance.now();
            options?.onMetricUpdate?.(() => ({ firstTokenMs: null, totalLatencyMs: null, iterationCount: null }));

            const emitLog = (stage: LogEntry['stage'], message: string, meta?: Record<string, unknown>) => {
                options?.onLog?.({
                    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    timestamp: new Date().toLocaleTimeString(),
                    stage,
                    message,
                    meta
                });
            };

            emitLog('ROUTER', `Initiating autonomous DAG orchestration for: "${query.slice(0, 60)}${query.length > 60 ? '...' : ''}"`);

            try {
                const headers: Record<string, string> = {
                    'Content-Type': 'application/json'
                };
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                }
                if (byokKey) {
                    headers['X-User-API-Key'] = byokKey;
                }

                const response = await fetch(`${API_BASE}/api/agent/stream`, {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        query,
                        documentId: documentId || undefined,
                        sessionId: existingSessionId || undefined
                    }),
                    signal: controller.signal
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new AgentStreamError(describeHttpError(response.status, errText), response.status);
                }

                if (!response.body) {
                    throw new AgentStreamError('Response body is null');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                let receivedFirstToken = false;
                let serverError: string | null = null;
                let finalDonePayload: AgentInvokeResponse | null = null;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const events = buffer.split('\n\n');
                    buffer = events.pop() || '';

                    for (const eventBlock of events) {
                        if (!eventBlock.trim()) continue;

                        let eventType = 'message';
                        let dataStr = '';

                        for (const line of eventBlock.split('\n')) {
                            if (line.startsWith('event:')) {
                                eventType = line.slice(6).trim();
                            } else if (line.startsWith('data:')) {
                                dataStr = line.slice(5).trim();
                            }
                        }

                        if (!dataStr) continue;

                        try {
                            const data = JSON.parse(dataStr);

                            switch (eventType) {
                                case 'start':
                                    setSessionId(data.sessionId);
                                    emitLog('ROUTER', `DAG Pipeline active: Session ${data.sessionId.slice(0, 8)}`);
                                    break;

                                case 'node_start':
                                    setCurrentNode(data.node);
                                    emitLog('INFERENCE', `Executing DAG node: [${data.node.toUpperCase()}]`);
                                    break;

                                case 'plan':
                                    if (Array.isArray(data.plan)) {
                                        setPlan(data.plan);
                                        emitLog('ROUTER', `Generated ${data.plan.length}-step execution plan`);
                                    }
                                    break;

                                case 'tool_result':
                                    if (data.tool === 'hybrid_rag_search' && Array.isArray(data.citations)) {
                                        setCitations(data.citations);
                                        emitLog('RAG', `Retrieved ${data.chunksRetrieved || data.citations.length} verified context chunks`);
                                    }
                                    break;

                                case 'critic': {
                                    const score =
                                        data.reflectionScore !== undefined ? data.reflectionScore : data.soundnessScore !== undefined ? data.soundnessScore : 0;
                                    setReflectionScore(score);
                                    setIsGrounded(!!data.isGrounded);
                                    emitLog('INFERENCE', `Critic Score: ${score} (${data.isGrounded ? 'GROUNDED' : 'REPLAN'}) - ${data.feedback || ''}`);
                                    break;
                                }

                                case 'token':
                                    if (data.token) {
                                        setStreamedResponse((prev) => prev + data.token);
                                        if (!receivedFirstToken) {
                                            receivedFirstToken = true;
                                            const firstTokenMs = Math.round(performance.now() - startTime);
                                            options?.onMetricUpdate?.((prev) => ({ ...prev, firstTokenMs }));
                                        }
                                    }
                                    break;

                                case 'done':
                                    finalDonePayload = data as AgentInvokeResponse;
                                    if (data.response !== undefined) setStreamedResponse(data.response);
                                    if (data.mermaidDiagrams !== undefined) setMermaidDiagrams(data.mermaidDiagrams);
                                    if (data.plan !== undefined) setPlan(data.plan);
                                    if (data.citations !== undefined) setCitations(data.citations);
                                    const doneScore = data.reflectionScore !== undefined ? data.reflectionScore : data.soundnessScore;
                                    if (doneScore !== undefined) setReflectionScore(doneScore);
                                    if (data.isGrounded !== undefined) setIsGrounded(!!data.isGrounded);
                                    setIsComplete(true);
                                    {
                                        const totalLatencyMs = Math.round(performance.now() - startTime);
                                        const iterationCount = typeof data.iterationCount === 'number' ? data.iterationCount : null;
                                        options?.onMetricUpdate?.((prev) => ({ ...prev, totalLatencyMs, iterationCount }));
                                        emitLog('STREAM', `DAG completed successfully. Total latency: ${totalLatencyMs}ms`);
                                    }
                                    break;

                                case 'error':
                                    serverError = data.error || 'Unknown SSE stream error';
                                    setStreamError(serverError);
                                    emitLog('ROUTER', `Stream Error: ${data.error}`);
                                    break;
                            }
                        } catch (parseErr) {
                            console.error('Failed to parse SSE data packet:', parseErr, dataStr);
                        }
                    }
                }

                if (!finalDonePayload) {
                    throw new AgentStreamError(serverError || 'The stream ended before a response was produced.');
                }

                setIsStreaming(false);
                return finalDonePayload;
            } catch (err: unknown) {
                if (err instanceof Error && err.name === 'AbortError') {
                    emitLog('STREAM', 'Execution cancelled by user');
                    return null;
                }
                const msg = err instanceof Error ? err.message : String(err);
                setStreamError(msg);
                emitLog('ROUTER', `Fatal stream error: ${msg}`);
                setIsStreaming(false);
                throw err instanceof AgentStreamError ? err : new AgentStreamError(msg);
            }
        },
        [options, cancelStream]
    );

    return {
        isStreaming,
        streamError,
        plan,
        currentNode,
        citations,
        streamedResponse,
        mermaidDiagrams,
        reflectionScore,
        isGrounded,
        isComplete,
        sessionId,
        startStream,
        cancelStream
    };
}
