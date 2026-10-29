import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { McpInspector } from './McpInspector';
import { useAuthStore } from '@/lib/auth-store';

describe('McpInspector Component', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuthStore.setState({ token: 'test-jwt-token' });
    });

    afterEach(() => {
        vi.restoreAllMocks();
        useAuthStore.setState({ token: null });
    });

    it('renders inspector header, tool name, and default arguments', () => {
        render(<McpInspector />);

        expect(screen.getByText('MCP Tool Inspector')).toBeInTheDocument();
        expect(screen.getByText('2024-11-05')).toBeInTheDocument();
        expect(screen.getByText('RAG Search')).toBeInTheDocument();
        expect(screen.queryByText('Python Sandbox')).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Invoke Tool/i })).toBeInTheDocument();
    });

    it('asks signed-out users to sign in instead of offering a call that would 401', () => {
        useAuthStore.setState({ token: null });
        const onOpenSignIn = vi.fn();
        render(<McpInspector onOpenSignIn={onOpenSignIn} />);

        expect(screen.queryByRole('button', { name: /Invoke Tool/i })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Sign in to try MCP tools/i }));
        expect(onOpenSignIn).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole('button', { name: /Copy access token/i })).not.toBeInTheDocument();
    });

    it('dispatches JSON-RPC 2.0 tool call to /api/mcp/v1 with the bearer token and renders the result', async () => {
        const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                jsonrpc: '2.0',
                id: 'client-123',
                result: { content: [{ text: 'Calculated: 42' }], isError: false }
            })
        });
        global.fetch = mockFetch;

        render(<McpInspector />);
        fireEvent.click(screen.getByRole('button', { name: /Invoke Tool/i }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));

        const [url, options] = mockFetch.mock.calls[0];
        expect(String(url)).toMatch(/\/api\/mcp\/v1$/);
        expect(options.method).toBe('POST');
        expect(options.headers.get('Authorization')).toBe('Bearer test-jwt-token');

        const parsedBody = JSON.parse(options.body);
        expect(parsedBody.method).toBe('tools/call');
        expect(parsedBody.params.name).toBe('hybrid_rag_search');

        await waitFor(() => {
            expect(screen.getByText('Success')).toBeInTheDocument();
            expect(screen.getByText('Calculated: 42')).toBeInTheDocument();
        });
    });

    it('surfaces JSON-RPC errors', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ jsonrpc: '2.0', id: 'x', error: { code: -32602, message: 'query: Field required' } })
        });

        render(<McpInspector />);
        fireEvent.click(screen.getByRole('button', { name: /Invoke Tool/i }));

        await waitFor(() => expect(screen.getByText('query: Field required')).toBeInTheDocument());
    });

    it('handles invalid JSON gracefully without throwing', async () => {
        render(<McpInspector />);

        fireEvent.change(screen.getByLabelText('MCP Tool Arguments JSON'), { target: { value: '{ invalid json' } });
        fireEvent.click(screen.getByRole('button', { name: /Invoke Tool/i }));

        await waitFor(() => expect(screen.getByText(/Invalid JSON arguments:/i)).toBeInTheDocument());
    });
});
