import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { McpInspector } from './McpInspector';

describe('McpInspector Component', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('renders inspector header, tool name, and default arguments', () => {
        render(<McpInspector apiBase="http://localhost:8000" />);

        expect(screen.getByText('MCP v2 Protocol Inspector')).toBeInTheDocument();
        expect(screen.getByText('v2024-11-05')).toBeInTheDocument();
        expect(screen.getByText('RAG Search')).toBeInTheDocument();
        expect(screen.queryByText('Python Sandbox')).not.toBeInTheDocument();
        expect(screen.queryByText('SQL Audit')).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Invoke Tool/i })).toBeInTheDocument();
    });

    it('dispatches JSON-RPC 2.0 tool call to /api/mcp/v1 and renders response', async () => {
        const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                jsonrpc: '2.0',
                id: 'client-123',
                result: {
                    content: [{ text: 'Calculated: 42' }],
                    isError: false
                }
            })
        });
        global.fetch = mockFetch;

        render(<McpInspector apiBase="http://localhost:8000" authToken="test-jwt-token" />);

        const invokeBtn = screen.getByRole('button', { name: /Invoke Tool/i });
        fireEvent.click(invokeBtn);

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });

        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toBe('http://localhost:8000/api/mcp/v1');
        expect(options.method).toBe('POST');
        expect(options.headers.Authorization).toBe('Bearer test-jwt-token');

        const parsedBody = JSON.parse(options.body);
        expect(parsedBody.method).toBe('tools/call');
        expect(parsedBody.params.name).toBe('hybrid_rag_search');

        await waitFor(() => {
            expect(screen.getByText('RPC 200 OK')).toBeInTheDocument();
            expect(screen.getByText('Calculated: 42')).toBeInTheDocument();
        });
    });

    it('handles invalid JSON gracefully without throwing', async () => {
        render(<McpInspector apiBase="http://localhost:8000" />);

        const textarea = screen.getByLabelText('MCP Tool Arguments JSON');
        fireEvent.change(textarea, { target: { value: '{ invalid json' } });

        const invokeBtn = screen.getByRole('button', { name: /Invoke Tool/i });
        fireEvent.click(invokeBtn);

        await waitFor(() => {
            expect(screen.getByText(/Invalid JSON arguments:/i)).toBeInTheDocument();
        });
    });
});
