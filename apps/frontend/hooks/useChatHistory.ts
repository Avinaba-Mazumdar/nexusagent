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
    const storageKey = React.useMemo(() => `nexusagent_chat_history_${user?.id || 'anonymous'}`, [user?.id]);

    const [conversations, setConversations] = React.useState<ChatConversation[]>(() => {
        if (typeof window === 'undefined') return [];
        try {
            const cached = localStorage.getItem(`nexusagent_chat_history_${user?.id || 'anonymous'}`);
            return cached ? JSON.parse(cached) : [];
        } catch {
            return [];
        }
    });

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

    const persistConversations = React.useCallback(
        (list: ChatConversation[]) => {
            try {
                localStorage.setItem(storageKey, JSON.stringify(list));
            } catch {
                // Ignore quota
            }
        },
        [storageKey]
    );

    const prefetchMessages = React.useCallback((convId: string) => {
        if (memoryMessageCache.current.has(convId)) return;
        try {
            const cached = localStorage.getItem(`nexusagent_msgs_${convId}`);
            if (cached) {
                memoryMessageCache.current.set(convId, JSON.parse(cached));
                return;
            }
        } catch {
            // Ignore
        }

        apiClient<ChatConversationDetailResponse>(`/api/chat/history/${convId}`)
            .then((detail) => {
                if (detail?.messages) {
                    memoryMessageCache.current.set(convId, detail.messages);
                    try {
                        localStorage.setItem(`nexusagent_msgs_${convId}`, JSON.stringify(detail.messages));
                    } catch {
                        // Ignore
                    }
                }
            })
            .catch(() => {
                // Silently ignore
            });
    }, []);

    const loadConversations = React.useCallback(
        async (force = false) => {
            if (!isGoogleUser || inFlightConversationsRef.current) return;
            const now = Date.now();
            if (!force && now - lastFetchConversationsRef.current < 8000) return;

            inFlightConversationsRef.current = true;
            setIsLoadingConversations(true);
            try {
                const cached = localStorage.getItem(storageKey);
                if (cached) {
                    setConversations((prev) => (prev.length === 0 ? JSON.parse(cached) : prev));
                }
            } catch {
                // Ignore
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
        [isGoogleUser, storageKey, prefetchMessages, persistConversations]
    );

    React.useEffect(() => {
        if (isGoogleUser) {
            void loadConversations();
        } else {
            setConversations([]);
        }
    }, [isGoogleUser, loadConversations]);

    const handleSelectConversation = React.useCallback((conversationId: string, _title: string, historyMessages?: ChatMessageRecord[], isLoading?: boolean) => {
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
            let initialMessages: ChatMessageRecord[] | undefined = memoryMessageCache.current.get(conv.id);
            if (!initialMessages) {
                try {
                    const cached = localStorage.getItem(`nexusagent_msgs_${conv.id}`);
                    if (cached) {
                        initialMessages = JSON.parse(cached);
                        if (initialMessages) memoryMessageCache.current.set(conv.id, initialMessages);
                    }
                } catch {
                    // Ignore
                }
            }

            const hasCached = Boolean(initialMessages && initialMessages.length > 0);
            handleSelectConversation(conv.id, conv.title, initialMessages, !hasCached);

            apiClient<ChatConversationDetailResponse>(`/api/chat/history/${conv.id}`)
                .then((detail) => {
                    if (detail?.messages) {
                        memoryMessageCache.current.set(conv.id, detail.messages);
                        try {
                            localStorage.setItem(`nexusagent_msgs_${conv.id}`, JSON.stringify(detail.messages));
                        } catch {
                            // Ignore
                        }
                        if (selectionRef.current !== conv.id) return;
                        handleSelectConversation(conv.id, conv.title, detail.messages, false);
                    }
                })
                .catch(() => {
                    // Ignore
                });
        },
        [handleSelectConversation]
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
                .then(() => {
                    memoryMessageCache.current.delete(convId);
                    try {
                        localStorage.removeItem(`nexusagent_msgs_${convId}`);
                    } catch {
                        // Ignore
                    }
                })
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
        [conversations, persistConversations, activeSessionId, handleNewChat]
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
        loadConversations,
        handleNewChat,
        handleSelectConversationItem,
        handleDeleteConversation,
        prefetchMessages,
        persistConversations
    };
}
