'use client';

import * as React from 'react';
import type {
    ChatConversation,
    ChatMessageRecord,
    ChatHistoryResponse,
    ChatConversationDetailResponse,
    Citation,
    InjectionWarning
} from '@nexusagent/contracts';
import { apiClient } from '@/lib/api-client';
import { readConversations, readMessages, removeMessages, writeConversations, writeMessages } from '@/lib/chat-cache';

export interface ChatItem {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: Citation[];
    warnings?: InjectionWarning[];
    query?: string;
    error?: string;
    stopped?: boolean;
}

/** Citations are stored with the assistant message so reloaded answers keep their source pills. */
function citationsOf(message: ChatMessageRecord): Citation[] | undefined {
    const stored = (message.reflectionSummary as { citations?: Citation[] } | null | undefined)?.citations;
    return Array.isArray(stored) && stored.length > 0 ? stored : undefined;
}

function byRecency(a: ChatConversation, b: ChatConversation): number {
    return (b.updatedAt || b.createdAt).localeCompare(a.updatedAt || a.createdAt);
}

export function useChatHistory(user: { id: string; isGuest?: boolean } | null) {
    const isGoogleUser = Boolean(user && !user.isGuest);
    const userId = user?.id;

    const [conversations, setConversations] = React.useState<ChatConversation[]>(() => (typeof window === 'undefined' ? [] : readConversations(userId)));

    const [isLoadingConversations, setIsLoadingConversations] = React.useState(false);
    const [chatSearchQuery, setChatSearchQuery] = React.useState('');
    const [chatNotice, setChatNotice] = React.useState<string | null>(null);
    const [messages, setMessages] = React.useState<ChatItem[]>([]);
    const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);

    const inFlightConversationsRef = React.useRef(false);
    const lastFetchConversationsRef = React.useRef<number>(0);
    const memoryMessageCache = React.useRef(new Map<string, ChatMessageRecord[]>());
    // The conversation the user selected last; a slower response for an earlier click is dropped.
    const selectionRef = React.useRef<string | null>(null);

    // Clear messages and active conversation when user changes
    React.useEffect(() => {
        memoryMessageCache.current.clear();
        lastFetchConversationsRef.current = 0;
        setConversations([]);
        setMessages([]);
        setActiveSessionId(null);
    }, [user?.id]);

    const persistConversations = React.useCallback((list: ChatConversation[]) => writeConversations(userId, list), [userId]);

    /** Memory first, then localStorage; null when this conversation has not been cached yet. */
    const cachedMessages = React.useCallback((convId: string): ChatMessageRecord[] | null => {
        const inMemory = memoryMessageCache.current.get(convId);
        if (inMemory) return inMemory;
        const stored = readMessages(convId);
        if (stored) memoryMessageCache.current.set(convId, stored);
        return stored;
    }, []);

    const storeMessages = React.useCallback((convId: string, records: ChatMessageRecord[]) => {
        memoryMessageCache.current.set(convId, records);
        writeMessages(convId, records);
    }, []);

    /** Forget the cached transcript so the next open fetches the server copy (call after a new answer is saved). */
    const invalidateMessages = React.useCallback((convId: string) => {
        memoryMessageCache.current.delete(convId);
        removeMessages(convId);
    }, []);

    const prefetchMessages = React.useCallback(
        (convId: string) => {
            if (cachedMessages(convId)) return;

            apiClient<ChatConversationDetailResponse>(`/api/chat/history/${convId}`)
                .then((detail) => {
                    if (detail?.messages) storeMessages(convId, detail.messages);
                })
                .catch(() => {
                    // Silently ignore
                });
        },
        [cachedMessages, storeMessages]
    );

    const loadConversations = React.useCallback(
        async (force = false) => {
            if (!isGoogleUser || inFlightConversationsRef.current) return;
            const now = Date.now();
            if (!force && now - lastFetchConversationsRef.current < 8000) return;

            inFlightConversationsRef.current = true;
            setIsLoadingConversations(true);
            const cached = readConversations(userId);
            if (cached.length > 0) {
                setConversations((prev) => (prev.length === 0 ? cached : prev));
            }

            try {
                const data = await apiClient<ChatHistoryResponse>('/api/chat/history');
                if (data?.conversations) {
                    lastFetchConversationsRef.current = Date.now();
                    setConversations(data.conversations);
                    persistConversations(data.conversations);

                    data.conversations.slice(0, 5).forEach((conv) => {
                        prefetchMessages(conv.id);
                    });
                }
            } catch {
                // Fallback to local cache
            } finally {
                inFlightConversationsRef.current = false;
                setIsLoadingConversations(false);
            }
        },
        [isGoogleUser, userId, prefetchMessages, persistConversations]
    );

    React.useEffect(() => {
        if (isGoogleUser) {
            void loadConversations();
        } else {
            setConversations([]);
        }
    }, [isGoogleUser, loadConversations]);

    const handleSelectConversation = React.useCallback((conversationId: string, historyMessages?: ChatMessageRecord[], isLoading?: boolean) => {
        setActiveSessionId(conversationId);
        if (historyMessages && historyMessages.length > 0) {
            setMessages(
                historyMessages.map((m) => ({
                    id: m.id,
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                    citations: citationsOf(m)
                }))
            );
        } else if (isLoading) {
            setMessages([]);
        }
    }, []);

    const handleNewChat = React.useCallback(() => {
        selectionRef.current = null;
        setActiveSessionId(null);
        setMessages([]);
    }, []);

    const handleSelectConversationItem = React.useCallback(
        (conv: ChatConversation) => {
            selectionRef.current = conv.id;
            const initialMessages = cachedMessages(conv.id) ?? undefined;

            const hasCached = Boolean(initialMessages && initialMessages.length > 0);
            handleSelectConversation(conv.id, initialMessages, !hasCached);

            apiClient<ChatConversationDetailResponse>(`/api/chat/history/${conv.id}`)
                .then((detail) => {
                    if (detail?.messages) {
                        storeMessages(conv.id, detail.messages);
                        if (selectionRef.current !== conv.id) return;
                        handleSelectConversation(conv.id, detail.messages, false);
                    }
                })
                .catch(() => {
                    // Ignore
                });
        },
        [handleSelectConversation, cachedMessages, storeMessages]
    );

    const handleDeleteConversation = React.useCallback(
        (convId: string) => {
            const removed = conversations.find((c) => c.id === convId);
            if (!removed) return;

            const remaining = conversations.filter((c) => c.id !== convId);
            setConversations(remaining);
            persistConversations(remaining);
            setChatNotice(null);

            if (activeSessionId === convId) {
                handleNewChat();
            }

            apiClient(`/api/chat/history/${convId}`, { method: 'DELETE' })
                .then(() => invalidateMessages(convId))
                .catch(() => {
                    setConversations((prev) => {
                        if (prev.some((c) => c.id === convId)) return prev;
                        const restored = [...prev, removed].sort(byRecency);
                        persistConversations(restored);
                        return restored;
                    });
                    setChatNotice(`Couldn't delete "${removed.title}". It has been restored.`);
                });
        },
        [conversations, persistConversations, activeSessionId, handleNewChat, invalidateMessages]
    );

    return {
        conversations,
        setConversations,
        isLoadingConversations,
        chatSearchQuery,
        setChatSearchQuery,
        chatNotice,
        setChatNotice,
        messages,
        setMessages,
        activeSessionId,
        setActiveSessionId,
        handleNewChat,
        handleSelectConversationItem,
        handleDeleteConversation,
        prefetchMessages,
        persistConversations,
        invalidateMessages
    };
}
