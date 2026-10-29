import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CitationPill } from './CitationPill';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { Citation } from '@nexusagent/contracts';

const mockCitation: Citation = {
    id: 'cite-1',
    label: 'S1',
    chunkId: 'chk-1',
    documentId: 'doc-1',
    filename: 'RFC-104-Raft.md',
    startLine: 120,
    endLine: 145,
    headerPath: ['Consensus', 'Leader Election'],
    preview: 'In Raft, leader election is initiated when a follower election timeout elapses.'
};

const renderPill = (citation: Citation, onClick?: (c: Citation) => void) =>
    render(
        <TooltipProvider>
            <CitationPill citation={citation} onClick={onClick} />
        </TooltipProvider>
    );

describe('CitationPill Component', () => {
    it('renders label, filename and line range badge', () => {
        renderPill(mockCitation);

        expect(screen.getByText('S1')).toBeInTheDocument();
        expect(screen.getByText('RFC-104-Raft.md')).toBeInTheDocument();
        expect(screen.getByText('L120-145')).toBeInTheDocument();
    });

    it('renders single line notation when startLine equals endLine', () => {
        renderPill({ ...mockCitation, filename: 'benchmark.md', startLine: 42, endLine: 42 });

        expect(screen.getByText('L42')).toBeInTheDocument();
    });

    it('passes the full citation to onClick', () => {
        const handleClick = vi.fn();
        renderPill(mockCitation, handleClick);

        fireEvent.click(screen.getByTestId('citation-pill'));

        expect(handleClick).toHaveBeenCalledTimes(1);
        expect(handleClick).toHaveBeenCalledWith(mockCitation);
    });
});
