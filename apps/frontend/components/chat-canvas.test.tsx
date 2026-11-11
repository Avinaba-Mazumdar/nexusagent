import * as React from 'react';
import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vite-plus/test';
import type { ChatConversation, ChatMessageRecord } from '@nexusagent/contracts';
import { apiClient } from '@/lib/api-client';
import { useChatHistory } from '@/hooks/useChatHistory';
import { ChatCanvas } from './chat-canvas';

vi.mock('@/lib/api-client', () => ({ apiClient: vi.fn() }));

function reloadedAnswer(uncited: boolean): ChatMessageRecord {
    return {
        id: 'm-1',
        conversationId: 'c-1',
        role: 'assistant',
        content: 'An answer from history',
        createdAt: '2026-01-01T00:00:00Z',
        reflectionSummary: { grounding: 'grounded', citations: [], webSources: [], uncited }
    } as unknown as ChatMessageRecord;
}

const conversation = {
    id: 'c-1',
    userId: 'u1',
    title: 'Chat',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    messageCount: 1,
    lastSnippet: ''
} as ChatConversation;

async function renderReloaded(uncited: boolean) {
    vi.mocked(apiClient).mockResolvedValue({ conversation, messages: [reloadedAnswer(uncited)] } as never);
    const { result } = renderHook(() => useChatHistory({ id: 'u1', isGuest: true }));
    act(() => result.current.handleSelectConversationItem(conversation));
    await waitFor(() => expect(result.current.messages).toHaveLength(1));
    render(
        <ChatCanvas
            mobileActiveTab="chat"
            user={null}
            quotaRemaining={5}
            quotaResetsAt={null}
            messages={result.current.messages}
            isStreaming={false}
            streamedResponse=""
            citations={[]}
            currentNode={null}
            streamingMsgId={null}
            liveStatus=""
            sessionNotice={null}
            onSignIn={vi.fn()}
            scrollContainerRef={React.createRef<HTMLDivElement>()}
            onScroll={vi.fn()}
            onNewChat={vi.fn()}
            onRetry={vi.fn()}
            onCitationClick={vi.fn()}
            onHireMeClick={vi.fn()}
            onSelectPrompt={vi.fn()}
        >
            {null}
        </ChatCanvas>
    );
}

describe('ChatCanvas - uncited warning on a reloaded chat (R6)', () => {
    it('shows the warning when the saved answer was uncited', async () => {
        await renderReloaded(true);
        expect(screen.getByText('An answer from history')).toBeInTheDocument();
        expect(screen.getByTestId('uncited-warning')).toBeInTheDocument();
    });

    it('shows no warning when the saved answer cited its sources', async () => {
        await renderReloaded(false);
        expect(screen.getByText('An answer from history')).toBeInTheDocument();
        expect(screen.queryByTestId('uncited-warning')).not.toBeInTheDocument();
    });
});
