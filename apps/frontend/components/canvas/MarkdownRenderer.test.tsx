import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarkdownRenderer } from './MarkdownRenderer';
import type { Citation } from '@nexusagent/contracts';

vi.mock('mermaid', () => ({
    default: {
        initialize: vi.fn(),
        render: vi.fn().mockResolvedValue({ svg: '<svg data-testid="mock-mermaid-svg"></svg>' })
    }
}));

describe('MarkdownRenderer Component', () => {
    const mockCitations: Citation[] = [
        {
            id: 'c-1',
            chunkId: 'chk-1',
            documentId: 'd-1',
            filename: 'benchlm_evals.md',
            startLine: 15,
            endLine: 30,
            headerPath: ['Benchmarks', 'Reasoning'],
            preview: 'Gemini 2.5 Flash demonstrates high inference speed.'
        }
    ];

    it('renders headings and list elements correctly', () => {
        const markdown = `
# Executive Overview
## Consensus Invariants
- First requirement
- Second requirement
`;
        render(<MarkdownRenderer content={markdown} />);

        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Executive Overview');
        expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Consensus Invariants');
        expect(screen.getByText('First requirement')).toBeInTheDocument();
        expect(screen.getByText('Second requirement')).toBeInTheDocument();
    });

    it('renders code blocks with language badge', () => {
        const markdown = '```python\nprint("hello world")\n```';
        render(<MarkdownRenderer content={markdown} />);

        expect(screen.getByText('python')).toBeInTheDocument();
        expect(screen.getByText('print("hello world")')).toBeInTheDocument();
    });

    it('renders inline citation pills matching citation metadata', () => {
        const markdown = 'Grounding evidence verified in [benchlm_evals.md (Lines 15-30)].';
        render(<MarkdownRenderer content={markdown} citations={mockCitations} />);

        expect(screen.getAllByText('benchlm_evals.md').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('L15-30').length).toBeGreaterThanOrEqual(1);
    });

    it('renders grounding citations tray at bottom when citations exist', () => {
        render(<MarkdownRenderer content="Analyzed models." citations={mockCitations} />);

        expect(screen.getByText('Grounding Citations:')).toBeInTheDocument();
    });

    it('renders structured markdown tables with headers and rows', () => {
        const markdown = `
| Dimension | Opus 5.5 | Gemini 3.8 Flash |
| :--- | :---: | ---: |
| Latency | 2800ms | 250ms |
| Cost | High | Low |
`;
        render(<MarkdownRenderer content={markdown} />);

        expect(screen.getByRole('table')).toBeInTheDocument();
        expect(screen.getByText('Dimension')).toBeInTheDocument();
        expect(screen.getByText('Opus 5.5')).toBeInTheDocument();
        expect(screen.getByText('Gemini 3.8 Flash')).toBeInTheDocument();
        expect(screen.getByText('Latency')).toBeInTheDocument();
        expect(screen.getByText('250ms')).toBeInTheDocument();
    });

    it('renders styled callout boxes with alert badges', () => {
        const markdown = `
> [!NOTE]
> This is a key architectural takeaway.
`;
        render(<MarkdownRenderer content={markdown} />);

        expect(screen.getByText('NOTE')).toBeInTheDocument();
        expect(screen.getByText('This is a key architectural takeaway.')).toBeInTheDocument();
    });

    it('renders categorized section headers with numbered badges', () => {
        const markdown = `
### 1. STRUCTURAL METRIC & WORKLOAD COMPARISON
Detailed analysis here.
`;
        render(<MarkdownRenderer content={markdown} />);

        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('STRUCTURAL METRIC & WORKLOAD COMPARISON')).toBeInTheDocument();
    });
});
