import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import { useAuthStore } from '@/lib/auth-store';
import Home from './page';

const startStream = vi.fn();

vi.mock('@/hooks/useAgentStream', async (importOriginal) => {
    const original = await importOriginal<typeof import('@/hooks/useAgentStream')>();
    return {
        ...original,
        useAgentStream: () => ({
            isStreaming: false,
            streamedResponse: '',
            citations: [],
            currentNode: null,
            plan: [],
            grounding: null,
            startStream,
            cancelStream: vi.fn()
        })
    };
});

function doneResult(conversationId: string | null) {
    return {
        sessionId: 'session-1',
        conversationId,
        response: 'Raft elects a leader.',
        citations: [],
        injectionWarnings: []
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
            token: 'token',
            user: { id: 'u1', name: 'Ada', email: 'ada@example.com', isGuest: false, createdAt: '', lastSeenAt: '' },
            quotaRemaining: 5,
            bucketCapacity: 25
        });
    });

    async function ask() {
        const user = userEvent.setup();
        render(<Home />);
        await user.type(screen.getByLabelText(/architecture question/i), 'Explain Raft');
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

        await screen.findByText('Raft elects a leader.');
        expect(screen.queryByText(/could not be saved to your history/i)).not.toBeInTheDocument();
    });
});
