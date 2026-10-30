'use client';

import * as React from 'react';
import type { AgentInvokeResponse, Citation, Grounding, PlanStep } from '@nexusagent/contracts';
import type { LogEntry, TelemetryMetrics } from '@/components/observability-panel';

import { API_BASE, getAuthToken, notifyUnauthorized } from '@/lib/api-client';

export interface UseAgentStreamOptions {
    onLog?: (entry: LogEntry) => void;
    onMetricUpdate?: (updater: (prev: TelemetryMetrics) => TelemetryMetrics) => void;
    onQuota?: (remaining: number) => void;
}

export interface StreamParams {
    query: string;
    documentId?: string | null;
    sessionId?: string | null;
}

/** Raised for HTTP failures and server-side stream errors so callers can render them. */
export class AgentStreamError extends Error {
    constructor(
        message: string,
        readonly status?: number,
        /** Seconds until quota refills, from the 429 Retry-After header. */
        readonly retryAfterSeconds?: number
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

/** The `done` payload plus the answer text, which arrives only as `token` (and `redact`) events. */
export type AgentRunResult = AgentInvokeResponse & { response: string };

/** Parse one SSE block: `event:` name plus all `data:` lines joined with a newline, per the SSE spec. */
export function parseSseBlock(block: string): { eventType: string; data: string } {
    let eventType = 'message';
    const dataLines: string[] = [];
    for (const line of block.split('\n')) {
        if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).replace(/^ /, ''));
        }
    }
    return { eventType, data: dataLines.join('\n') };
}

export function useAgentStream(options?: UseAgentStreamOptions) {
    const [isStreaming, setIsStreaming] = React.useState(false);
    const [streamError, setStreamError] = React.useState<string | null>(null);
    const [plan, setPlan] = React.useState<PlanStep[]>([]);
    const [currentNode, setCurrentNode] = React.useState<string | null>(null);
    const [citations, setCitations] = React.useState<Citation[]>([]);
    const [streamedResponse, setStreamedResponse] = React.useState('');
    const [grounding, setGrounding] = React.useState<Grounding | null>(null);

    const abortControllerRef = React.useRef<AbortController | null>(null);

    const cancelStream = React.useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsStreaming(false);
    }, []);

    const startStream = React.useCallback(
        async (params: StreamParams): Promise<AgentRunResult | null> => {
            const { query, documentId, sessionId: existingSessionId } = params;

            cancelStream();

            setIsStreaming(true);
            setStreamError(null);
            setPlan([]);
            setCurrentNode(null);
            setCitations([]);
            setStreamedResponse('');
            setGrounding(null);

            const controller = new AbortController();
            abortControllerRef.current = controller;
            const startTime = performance.now();
            options?.onMetricUpdate?.(() => ({ firstTokenMs: null, totalLatencyMs: null }));

            const emitLog = (stage: LogEntry['stage'], message: string) => {
                options?.onLog?.({
                    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    timestamp: new Date().toLocaleTimeString(),
                    stage,
                    message
                });
            };

            emitLog('ROUTER', `Starting run for: "${query.slice(0, 60)}${query.length > 60 ? '...' : ''}"`);

            try {
                const headers: Record<string, string> = {
                    'Content-Type': 'application/json'
                };
                const token = getAuthToken();
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
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
                    if (response.status === 401) notifyUnauthorized();
                    const retryAfter = Number(response.headers?.get?.('Retry-After'));
                    throw new AgentStreamError(
                        describeHttpError(response.status, errText),
                        response.status,
                        Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined
                    );
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
                let answer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
                    const events = buffer.split('\n\n');
                    buffer = events.pop() || '';

                    for (const eventBlock of events) {
                        if (!eventBlock.trim()) continue;

                        const { eventType, data: dataStr } = parseSseBlock(eventBlock);
                        if (!dataStr) continue;

                        try {
                            const data = JSON.parse(dataStr);

                            switch (eventType) {
                                case 'start':
                                    if (typeof data.quotaRemaining === 'number') {
                                        options?.onQuota?.(data.quotaRemaining);
                                    }
                                    emitLog('ROUTER', `Session ${data.sessionId.slice(0, 8)} started`);
                                    break;

                                case 'node_start':
                                    setCurrentNode(data.node);
                                    emitLog('INFERENCE', `Running step: ${data.node}`);
                                    break;

                                case 'plan':
                                    if (Array.isArray(data.plan)) {
                                        setPlan(data.plan);
                                        emitLog('ROUTER', `Planned ${data.plan.length} steps`);
                                    }
                                    break;

                                case 'tool_result':
                                    if (data.tool === 'hybrid_rag_search' && Array.isArray(data.citations)) {
                                        setCitations(data.citations);
                                        emitLog('RAG', `Retrieved ${data.chunksRetrieved ?? data.citations.length} source chunks`);
                                        for (const w of data.injectionWarnings ?? []) {
                                            emitLog('RAG', `Warning: ${w.filename} contains instruction-like text (${w.reason}). Treated as untrusted data.`);
                                        }
                                    }
                                    break;

                                case 'grounding':
                                    setGrounding(data.grounding);
                                    emitLog('INFERENCE', data.feedback || `Grounding: ${data.grounding}`);
                                    break;

                                case 'token':
                                    if (data.token) {
                                        answer += data.token;
                                        setStreamedResponse(answer);
                                        if (!receivedFirstToken) {
                                            receivedFirstToken = true;
                                            const firstTokenMs = Math.round(performance.now() - startTime);
                                            options?.onMetricUpdate?.((prev) => ({ ...prev, firstTokenMs }));
                                        }
                                    }
                                    break;

                                case 'done': {
                                    finalDonePayload = data as AgentInvokeResponse;
                                    if (data.plan !== undefined) setPlan(data.plan);
                                    if (data.citations !== undefined) setCitations(data.citations);
                                    if (data.grounding) setGrounding(data.grounding);
                                    if (data.model) emitLog('INFERENCE', `Answered by ${data.model}`);
                                    const totalLatencyMs = Math.round(performance.now() - startTime);
                                    options?.onMetricUpdate?.((prev) => ({ ...prev, totalLatencyMs }));
                                    emitLog('STREAM', `Run finished in ${totalLatencyMs}ms`);
                                    break;
                                }

                                case 'redact':
                                    answer = data.response;
                                    setStreamedResponse(answer);
                                    emitLog('STREAM', 'Answer withdrawn by the canary-token check');
                                    break;

                                case 'error':
                                    serverError = data.error || 'Unknown SSE stream error';
                                    setStreamError(serverError);
                                    emitLog('ROUTER', `Stream error: ${data.error}`);
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
                return { ...finalDonePayload, response: answer };
            } catch (err: unknown) {
                if (err instanceof Error && err.name === 'AbortError') {
                    emitLog('STREAM', 'Run cancelled');
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
        grounding,
        startStream,
        cancelStream
    };
}
