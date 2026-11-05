import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vite-plus/test';
import { McpInspector } from './McpInspector';
import { MCP_URL } from '@/lib/mcp-client-config';

describe('McpInspector Component', () => {
    let writeTextMock: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        vi.clearAllMocks();
        writeTextMock = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, {
            clipboard: {
                writeText: writeTextMock
            }
        });
    });

    it('renders header, public badge, and note', () => {
        render(<McpInspector />);

        expect(screen.getByText('Connect MCP Client')).toBeInTheDocument();
        expect(screen.getByText(/Public/)).toBeInTheDocument();
        expect(screen.getByText('Read-only. Searches the 4 public benchmark documents.')).toBeInTheDocument();
    });

    it('renders the MCP URL and allows copying it', async () => {
        render(<McpInspector />);

        expect(screen.getByText(MCP_URL)).toBeInTheDocument();
        const copyButton = screen.getByRole('button', { name: /Copy MCP URL/i });
        await act(async () => {
            fireEvent.click(copyButton);
        });

        expect(writeTextMock).toHaveBeenCalledWith(MCP_URL);
    });

    it('renders instructions for Claude and ChatGPT', () => {
        render(<McpInspector />);

        expect(screen.getByText(/Claude \(claude\.ai \/ Desktop\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Settings → Connectors → Add custom connector → paste the URL/i)).toBeInTheDocument();

        expect(screen.getByText('ChatGPT')).toBeInTheDocument();
        expect(screen.getByText(/Settings → Apps & Connectors → Advanced → Developer mode → Create connector → paste the URL, no auth/i)).toBeInTheDocument();
    });

    it('renders JSON client config for Cursor/Claude Code and allows copying it', async () => {
        render(<McpInspector />);

        const pre = screen.getByText(/airankagent/);
        expect(pre).toBeInTheDocument();
        expect(pre.textContent).toContain('"type": "http"');

        const copyJsonButton = screen.getByRole('button', { name: /Copy JSON config/i });
        await act(async () => {
            fireEvent.click(copyJsonButton);
        });

        expect(writeTextMock).toHaveBeenCalledWith(expect.stringContaining('"airankagent"'));
    });
});
