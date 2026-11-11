import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import { useAuthStore } from '@/lib/auth-store';
import Home from './page';

const startStream = vi.fn();
vi.mock('@/hooks/useAgentStream', () => ({
    useAgentStream: () => ({
        isStreaming: false,
        plan: [],
        currentNode: null,
        nodeHistory: [],
        citations: [],
        webSources: [],
        streamedResponse: '',
        grounding: null,
        startStream,
        cancelStream: vi.fn()
    })
}));

function doneResult(sessionId: string | null) {
    return {
        response: 'Raft consensus answer',
        plan: [],
        citations: [],
        webSources: [],
        grounding: 'grounded' as const,
        nodeHistory: [],
        sessionId
    };
}

describe('Home page - saving a Google user turn (R2-LOG-07)', () => {
    beforeEach(() => {
        localStorage.clear();
        startStream.mockReset();
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ documents: [], conversations: [] })
        } as unknown as Response);
        useAuthStore.setState({
            user: { id: 'u1', name: 'Ada', email: 'ada@example.com', isGuest: false, isAdmin: false, createdAt: '', lastSeenAt: '' },
            quotaRemaining: 5,
            bucketCapacity: 25
        });
    });

    async function ask() {
        const user = userEvent.setup();
        render(<Home />);
        await user.type(screen.getByLabelText(/benchmark question/i), 'Explain Raft');
        await act(async () => {
            await user.click(screen.getByRole('button', { name: /send query/i }));
        });
    }

    it('shows a notice and no sidebar item when the server could not save the turn', async () => {
        startStream.mockResolvedValue(doneResult(null));
        await ask();

        expect(await screen.findByText(/could not be saved to your history/i)).toBeInTheDocument();
    });

    it('shows no notice when the turn was saved', async () => {
        startStream.mockResolvedValue(doneResult('session-1'));
        await ask();

        expect(screen.queryByText(/could not be saved to your history/i)).not.toBeInTheDocument();
    });
});
