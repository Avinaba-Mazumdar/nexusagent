import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vite-plus/test';
import { SourceDialog } from './SourceDialog';
import type { Citation } from '@nexusagent/contracts';

const citation: Citation = {
    id: 'c1',
    label: 'S1',
    chunkId: 'chunk-2',
    documentId: 'doc-1',
    filename: 'benchlm_evals.md',
    startLine: 10,
    endLine: 14,
    headerPath: ['Benchmarks'],
    preview: 'short'
};

describe('SourceDialog', () => {
    afterEach(() => vi.restoreAllMocks());

    it('shows the cited passage fetched from the single-chunk endpoint', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ id: 'chunk-2', content: 'The full cited passage.' })
        } as unknown as Response);
        global.fetch = fetchMock;

        render(<SourceDialog citation={citation} onClose={() => {}} />);

        expect(await screen.findByTestId('source-passage')).toHaveTextContent('The full cited passage.');
        expect(screen.getByText('benchlm_evals.md')).toBeInTheDocument();
        expect(screen.getByText(/lines 10-14/)).toBeInTheDocument();
        expect(String(fetchMock.mock.calls[0][0])).toContain('/api/documents/doc-1/chunks/chunk-2');
    });

    it('explains when the passage is gone', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            statusText: 'Not Found',
            json: async () => ({ detail: 'Chunk not found' })
        } as unknown as Response);

        render(<SourceDialog citation={citation} onClose={() => {}} />);

        await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/no longer available/i));
    });

    it('renders nothing when there is no citation', () => {
        render(<SourceDialog citation={null} onClose={() => {}} />);
        expect(screen.queryByTestId('source-passage')).not.toBeInTheDocument();
    });
});
