import { act, render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApprovalModal } from './ApprovalModal';
import type { PendingApproval } from '@/hooks/useAgentStream';

describe('ApprovalModal Component', () => {
    const mockApproval: PendingApproval = {
        approvalId: 'hitl-9944a1b2',
        sessionId: 'sess-test-123',
        tool: 'mcp_sql_audit',
        arguments: {
            query: 'SELECT table_name FROM information_schema.tables;'
        },
        riskLevel: 'medium',
        timeoutSeconds: 15
    };

    it('returns null when approval is null', () => {
        const { container } = render(<ApprovalModal open={true} approval={null} onResolve={vi.fn()} />);
        expect(container.firstChild).toBeNull();
    });

    it('renders security authorization title, tool details, and payload', () => {
        render(<ApprovalModal open={true} approval={mockApproval} onResolve={vi.fn()} />);

        expect(screen.getByText('HITL Security Authorization Required')).toBeInTheDocument();
        expect(screen.getAllByText(/mcp_sql_audit/i)[0]).toBeInTheDocument();
        expect(screen.getByText('hitl-9944a1b2')).toBeInTheDocument();
        expect(screen.getByText(/medium risk/i)).toBeInTheDocument();
        expect(screen.getByText(/information_schema\.tables/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Authorize & Run/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Deny & Skip/i })).toBeInTheDocument();
    });

    it('triggers approve resolution on Authorize button click', () => {
        const handleResolve = vi.fn();
        render(<ApprovalModal open={true} approval={mockApproval} onResolve={handleResolve} />);

        const approveBtn = screen.getByRole('button', { name: /Authorize & Run/i });
        fireEvent.click(approveBtn);

        expect(handleResolve).toHaveBeenCalledWith('approve');
    });

    it('triggers reject resolution on Deny button click', () => {
        const handleResolve = vi.fn();
        render(<ApprovalModal open={true} approval={mockApproval} onResolve={handleResolve} />);

        const denyBtn = screen.getByRole('button', { name: /Deny & Skip/i });
        fireEvent.click(denyBtn);

        expect(handleResolve).toHaveBeenCalledWith('reject');
    });

    it('counts down and auto-denies when the server-side timeout lapses', () => {
        vi.useFakeTimers();
        const handleResolve = vi.fn();
        render(<ApprovalModal open={true} approval={{ ...mockApproval, timeoutSeconds: 3 }} onResolve={handleResolve} />);

        expect(screen.getByText('3s')).toBeInTheDocument();
        act(() => {
            vi.advanceTimersByTime(3000);
        });
        expect(handleResolve).toHaveBeenCalledWith('reject');
        vi.useRealTimers();
    });
});
