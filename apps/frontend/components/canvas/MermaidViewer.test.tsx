import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MermaidViewer } from './MermaidViewer';

vi.mock('mermaid', () => ({
    default: {
        initialize: vi.fn(),
        render: vi.fn().mockImplementation(async (id: string, code: string) => {
            if (code.includes('invalid_syntax')) {
                throw new Error('Parse error on line 1');
            }
            if (code.includes('xss_test')) {
                return {
                    svg: `<svg data-testid="xss-svg" id="${id}"><script>alert(1)</script><a href="javascript:alert(1)"><text>x</text></a><foreignObject><div onclick="alert(1)">Sanitized Label</div></foreignObject></svg>`
                };
            }
            return {
                svg: `<svg data-testid="mock-mermaid-svg" id="${id}"><g class="node"><foreignObject width="100" height="40"><div xmlns="http://www.w3.org/1999/xhtml"><span class="nodeLabel">Client App</span></div></foreignObject></g><text>Architecture Diagram</text></svg>`
            };
        })
    }
}));

describe('MermaidViewer Component', () => {
    const validChart = `
flowchart TD
    Client["Client App"] --> Leader["Raft Leader"]
`;

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders diagram title and toolbar controls', async () => {
        render(<MermaidViewer chart={validChart} title="Consensus Topology" />);

        expect(screen.getByText('Consensus Topology')).toBeInTheDocument();
        expect(screen.getByText('Mermaid.js SVG')).toBeInTheDocument();
        expect(screen.getByLabelText('Zoom diagram in')).toBeInTheDocument();
        expect(screen.getByLabelText('Zoom diagram out')).toBeInTheDocument();
        expect(screen.getByLabelText('Reset zoom and position')).toBeInTheDocument();

        await waitFor(() => {
            expect(screen.getByTestId('mock-mermaid-svg')).toBeInTheDocument();
        });
    });

    it('preserves foreignObject node labels and does not strip them', async () => {
        render(<MermaidViewer chart={validChart} />);

        await waitFor(() => {
            expect(screen.getByText('Client App')).toBeInTheDocument();
        });
    });

    it('sanitizes malicious script tags, javascript urls, and event handlers while preserving foreignObject', async () => {
        render(<MermaidViewer chart="xss_test" />);

        await waitFor(() => {
            const svg = screen.getByTestId('xss-svg');
            expect(svg).toBeInTheDocument();
            expect(svg.querySelector('script')).toBeNull();
            expect(svg.querySelector('a')?.getAttribute('href')).not.toBe('javascript:alert(1)');
            expect(svg.innerHTML).not.toContain('onclick');
            expect(screen.getByText('Sanitized Label')).toBeInTheDocument();
        });
    });

    it('toggles raw syntax view when code button is clicked', async () => {
        render(<MermaidViewer chart={validChart} />);

        await waitFor(() => {
            expect(screen.getByTestId('mock-mermaid-svg')).toBeInTheDocument();
        });

        const toggleBtn = screen.getByLabelText('View diagram source');
        fireEvent.click(toggleBtn);

        expect(screen.getByText(/flowchart TD/)).toBeInTheDocument();
    });

    it('maximizes as a dialog that closes on Escape or backdrop click', async () => {
        render(<MermaidViewer chart={validChart} title="Topology" />);

        fireEvent.click(screen.getByLabelText('Maximize diagram view'));
        expect(screen.getByRole('dialog', { name: 'Topology' })).toBeInTheDocument();

        fireEvent.keyDown(document, { key: 'Escape' });
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

        fireEvent.click(screen.getByLabelText('Maximize diagram view'));
        fireEvent.click(screen.getByTestId('mermaid-backdrop'));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('supports keyboard zoom on the focusable viewport', () => {
        render(<MermaidViewer chart={validChart} />);

        const viewport = screen.getByRole('group', { name: /diagram viewport/i });
        fireEvent.keyDown(viewport, { key: '+' });
        expect(screen.getByText('115%')).toBeInTheDocument();
        fireEvent.keyDown(viewport, { key: '0' });
        expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('handles diagram render error gracefully without crashing', async () => {
        render(<MermaidViewer chart="invalid_syntax" />);

        await waitFor(() => {
            expect(screen.getByText(/Diagram parsing in progress or syntax error/)).toBeInTheDocument();
            expect(screen.getByText(/Parse error on line 1/)).toBeInTheDocument();
        });
    });
});
