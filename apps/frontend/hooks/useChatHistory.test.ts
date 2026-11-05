import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import type { ChatConversation, ChatConversationDetailResponse } from '@nexusagent/contracts';
import { apiClient } from '@/lib/api-client';
import { useChatHistory } from './useChatHistory';

vi.mock('@/lib/api-client', () => ({ apiClient: vi.fn() }));

const conv = (id: string): ChatConversation => ({
    id,
    userId: 'u1',
    title: `Chat ${id}`,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    messageCount: 2,
    lastSnippet: ''
});

const detail = (id: string): ChatConversationDetailResponse =>
    ({
        conversation: conv(id),
        messages: [{ id: `m-${id}`, conversationId: id, role: 'user', content: `content of ${id}`, createdAt: '2026-01-01T00:00:00Z' }]
    }) as unknown as ChatConversationDetailResponse;

function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((r) => {
        resolve = r;
    });
    return { promise, resolve };
}

describe('useChatHistory', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.mocked(apiClient).mockReset();
    });

    it('keeps the last clicked conversation when responses arrive out of order (R2-LOG-06)', async () => {
        const slowA = deferred<ChatConversationDetailResponse>();
        const fastB = deferred<ChatConversationDetailResponse>();
        vi.mocked(apiClient).mockImplementation((path: string) => (path.endsWith('/a') ? slowA.promise : fastB.promise) as never);

        const { result } = renderHook(() => useChatHistory({ id: 'u1', isGuest: true }));

        act(() => result.current.handleSelectConversationItem(conv('a')));
        act(() => result.current.handleSelectConversationItem(conv('b')));

        await act(async () => {
            fastB.resolve(detail('b'));
            await fastB.promise;
        });
        await act(async () => {
            slowA.resolve(detail('a'));
            await slowA.promise;
        });

        expect(result.current.activeSessionId).toBe('b');
        expect(result.current.messages.map((m) => m.content)).toEqual(['content of b']);
    });

    it('restores a conversation and explains when the delete fails', async () => {
        const first = conv('a');
        vi.mocked(apiClient).mockImplementation((path: string, options?: { method?: string }) => {
            if (options?.method === 'DELETE') return Promise.reject(new Error('server down')) as never;
            return Promise.resolve({ conversations: [first] }) as never;
        });

        const { result } = renderHook(() => useChatHistory({ id: 'u1', isGuest: false }));
        await waitFor(() => expect(result.current.conversations).toHaveLength(1));

        act(() => result.current.handleDeleteConversation('a'));
        await waitFor(() => expect(result.current.chatNotice).toMatch(/couldn't delete/i));

        expect(result.current.conversations.map((c) => c.id)).toEqual(['a']);
    });
});
