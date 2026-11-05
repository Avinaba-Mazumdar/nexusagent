import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vite-plus/test';
import { useAgentStream } from './useAgentStream';

describe('useAgentStream Hook', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it('initializes with default idle state', () => {
        const { result } = renderHook(() => useAgentStream());

        expect(result.current.isStreaming).toBe(false);
        expect(result.current.plan).toEqual([]);
        expect(result.current.currentNode).toBeNull();
        expect(result.current.citations).toEqual([]);
        expect(result.current.streamedResponse).toBe('');
        expect(result.current.grounding).toBeNull();
    });

    it('processes SSE events stream correctly', async () => {
        const onQuotaMock = vi.fn();
        const encoder = new TextEncoder();
        const sseEvents = [
            'event: start\ndata: {"sessionId": "test-session-123", "quotaRemaining": 3}\n\n',
            'event: plan\ndata: {"plan": [{"id": "1", "description": "Step 1: Retrieve context", "status": "pending", "agent": "retriever"}]}\n\n',
            'event: node_start\ndata: {"node": "router", "status": "running"}\n\n',
            'event: token\ndata: {"token": "Hello "}\n\n',
            'event: token\ndata: {"token": "World!"}\n\n',
            'event: grounding\ndata: {"grounding": "grounded", "feedback": "Grounded in 1 retrieved sources."}\n\n',
            'event: done\ndata: {"sessionId": "test-session-123", "citations": [{"id": "c1", "chunkId": "chk1", "documentId": "d1", "filename": "doc.md", "headerPath": ["Architecture"], "preview": "Text"}]}\n\n'
        ];

        let index = 0;
        const mockStream = new ReadableStream({
            pull(controller) {
                if (index < sseEvents.length) {
                    controller.enqueue(encoder.encode(sseEvents[index]));
                    index++;
                } else {
                    controller.close();
                }
            }
        });

        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            body: mockStream,
            status: 200
        } as unknown as Response);

        const { result } = renderHook(() => useAgentStream({ onQuota: onQuotaMock }));

        let run: Awaited<ReturnType<typeof result.current.startStream>> = null;
        await act(async () => {
            run = await result.current.startStream({ query: 'What is the airankagent architecture?' });
        });

        expect(run).toMatchObject({ response: 'Hello World!' });
        expect(result.current.isStreaming).toBe(false);
        expect(onQuotaMock).toHaveBeenCalledWith(3);
        expect(result.current.plan.length).toBe(1);
        expect(result.current.streamedResponse).toBe('Hello World!');
        expect(result.current.grounding).toBe('grounded');
        expect(result.current.citations.length).toBe(1);
        expect(result.current.citations[0].filename).toBe('doc.md');
    });

    it('calls onUsage when a usage frame arrives', async () => {
        const onUsageMock = vi.fn();
        const encoder = new TextEncoder();
        const body = [
            'event: start\ndata: {"sessionId": "s"}\n\n',
            'event: usage\ndata: {"sessionId": "s", "step": "router", "model": "gemini-2.5-flash", "inputTokens": 45, "outputTokens": 10, "totalTokens": 55}\n\n',
            'event: token\ndata: {"sessionId": "s", "token": "Answer"}\n\n',
            'event: done\ndata: {"sessionId": "s", "citations": []}\n\n'
        ].join('');
        const mockStream = new ReadableStream({
            pull(controller) {
                controller.enqueue(encoder.encode(body));
                controller.close();
            }
        });
        global.fetch = vi.fn().mockResolvedValue({ ok: true, body: mockStream, status: 200 } as unknown as Response);

        const { result } = renderHook(() => useAgentStream({ onUsage: onUsageMock }));

        await act(async () => {
            await result.current.startStream({ query: 'Hello' });
        });

        expect(onUsageMock).toHaveBeenCalledWith(
            expect.objectContaining({
                step: 'router',
                model: 'gemini-2.5-flash',
                inputTokens: 45,
                outputTokens: 10,
                totalTokens: 55
            })
        );
    });

    it('calls onToolCall and logs for google_search tool call', async () => {
        const onToolCallMock = vi.fn();
        const onToolResultMock = vi.fn();
        const encoder = new TextEncoder();
        const body = [
            'event: start\ndata: {"sessionId": "s"}\n\n',
            'event: tool_call\ndata: {"sessionId": "s", "tool": "google_search", "arguments": {"queries": ["weather Kolkata"]}}\n\n',
            'event: tool_result\ndata: {"tool": "google_search", "chunksRetrieved": 1, "durationMs": 145}\n\n',
            'event: done\ndata: {"sessionId": "s", "citations": []}\n\n'
        ].join('');
        const mockStream = new ReadableStream({
            pull(controller) {
                controller.enqueue(encoder.encode(body));
                controller.close();
            }
        });
        global.fetch = vi.fn().mockResolvedValue({ ok: true, body: mockStream, status: 200 } as unknown as Response);

        const logs: Array<{ stage: string; message: string }> = [];
        const { result } = renderHook(() =>
            useAgentStream({
                onLog: (e) => logs.push(e),
                onToolCall: onToolCallMock,
                onToolResult: onToolResultMock
            })
        );

        await act(async () => {
            await result.current.startStream({ query: 'weather Kolkata' });
        });

        expect(onToolCallMock).toHaveBeenCalledWith({
            tool: 'google_search',
            args: { queries: ['weather Kolkata'] }
        });
        expect(onToolResultMock).toHaveBeenCalledWith({
            tool: 'google_search',
            chunksRetrieved: 1,
            durationMs: 145
        });
        expect(logs.some((l) => l.message.includes('Google Search: "weather Kolkata"'))).toBe(true);
    });

    it('handles stream HTTP error responses', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 403,
            text: async () => 'Rate limit exceeded or quota exhausted.'
        } as unknown as Response);

        const { result } = renderHook(() => useAgentStream());

        await act(async () => {
            await expect(result.current.startStream({ query: 'Hello' })).rejects.toThrow(/Rate limit exceeded/);
        });

        expect(result.current.isStreaming).toBe(false);
    });

    it('rejects with a quota message on 429 so the UI can surface it', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 429,
            text: async () => '{"detail": "Token bucket empty"}'
        } as unknown as Response);

        const { result } = renderHook(() => useAgentStream());

        await act(async () => {
            await expect(result.current.startStream({ query: 'Hello' })).rejects.toMatchObject({ status: 429 });
        });
    });

    it('rejects when the server emits an error event and no done payload', async () => {
        const encoder = new TextEncoder();
        const mockStream = new ReadableStream({
            pull(controller) {
                controller.enqueue(encoder.encode('event: error\ndata: {"error": "Synthesis failed"}\n\n'));
                controller.close();
            }
        });
        global.fetch = vi.fn().mockResolvedValue({ ok: true, body: mockStream, status: 200 } as unknown as Response);

        const { result } = renderHook(() => useAgentStream());

        await act(async () => {
            await expect(result.current.startStream({ query: 'Hello' })).rejects.toThrow('Synthesis failed');
        });
        expect(result.current.isStreaming).toBe(false);
    });

    it('logs the retrieval call before its result arrives', async () => {
        const encoder = new TextEncoder();
        const body = [
            'event: tool_call\ndata: {"sessionId": "s", "tool": "hybrid_rag_search", "arguments": {"query": "raft", "limit": 5, "documentScoped": false}}\n\n',
            'event: tool_result\ndata: {"tool": "hybrid_rag_search", "chunksRetrieved": 0, "citations": [], "injectionWarnings": []}\n\n',
            'event: done\ndata: {"sessionId": "s", "citations": []}\n\n'
        ].join('');
        const mockStream = new ReadableStream({
            pull(controller) {
                controller.enqueue(encoder.encode(body));
                controller.close();
            }
        });
        global.fetch = vi.fn().mockResolvedValue({ ok: true, body: mockStream, status: 200 } as unknown as Response);

        const logs: Array<{ stage: string; message: string }> = [];
        const { result } = renderHook(() => useAgentStream({ onLog: (entry) => logs.push(entry) }));

        await act(async () => {
            await result.current.startStream({ query: 'raft' });
        });

        const messages = logs.map((entry) => entry.message);
        const callIndex = messages.indexOf('Calling hybrid_rag_search over all sources (top 5)');
        expect(callIndex).toBeGreaterThan(-1);
        expect(logs[callIndex].stage).toBe('RAG');
        expect(messages.findIndex((m) => m.startsWith('Retrieved'))).toBeGreaterThan(callIndex);
    });

    it('names the selected document when the retrieval call is scoped to one', async () => {
        const encoder = new TextEncoder();
        const body =
            'event: tool_call\ndata: {"sessionId": "s", "tool": "hybrid_rag_search", "arguments": {"query": "q", "limit": 5, "documentScoped": true}}\n\n';
        const mockStream = new ReadableStream({
            pull(controller) {
                controller.enqueue(encoder.encode(body));
                controller.close();
            }
        });
        global.fetch = vi.fn().mockResolvedValue({ ok: true, body: mockStream, status: 200 } as unknown as Response);

        const logs: Array<{ message: string }> = [];
        const { result } = renderHook(() => useAgentStream({ onLog: (entry) => logs.push(entry) }));

        await act(async () => {
            await expect(result.current.startStream({ query: 'q' })).rejects.toThrow('The stream ended before a response was produced.');
        });
        expect(logs.map((entry) => entry.message)).toContain('Calling hybrid_rag_search over the selected document (top 5)');
    });
});
