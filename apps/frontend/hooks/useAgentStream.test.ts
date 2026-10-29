import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useAgentStream } from './useAgentStream';

describe('useAgentStream Hook', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it('initializes with default idle state', () => {
        const { result } = renderHook(() => useAgentStream());

        expect(result.current.isStreaming).toBe(false);
        expect(result.current.streamError).toBeNull();
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
            'event: node_start\ndata: {"node": "planner", "status": "running"}\n\n',
            'event: token\ndata: {"token": "Hello "}\n\n',
            'event: token\ndata: {"token": "World!"}\n\n',
            'event: grounding\ndata: {"grounding": "grounded", "feedback": "Grounded in 1 retrieved sources."}\n\n',
            'event: done\ndata: {"sessionId": "test-session-123", "response": "Hello World!", "citations": [{"id": "c1", "chunkId": "chk1", "documentId": "d1", "filename": "doc.md", "headerPath": ["Architecture"], "preview": "Text"}]}\n\n'
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

        await act(async () => {
            await result.current.startStream({ query: 'What is the nexusagent architecture?' });
        });

        expect(result.current.isStreaming).toBe(false);
        expect(onQuotaMock).toHaveBeenCalledWith(3);
        expect(result.current.plan.length).toBe(1);
        expect(result.current.streamedResponse).toBe('Hello World!');
        expect(result.current.grounding).toBe('grounded');
        expect(result.current.citations.length).toBe(1);
        expect(result.current.citations[0].filename).toBe('doc.md');
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
        expect(result.current.streamError).toContain('Rate limit exceeded');
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

        expect(result.current.streamError).toMatch(/quota exhausted/i);
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
});
