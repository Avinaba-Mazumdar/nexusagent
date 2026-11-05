import type { ChatConversation, ChatMessageRecord } from '@nexusagent/contracts';

const CONVERSATIONS_PREFIX = 'nexusagent_chat_history_';
const MESSAGES_PREFIX = 'nexusagent_msgs_';

function read<T>(key: string): T | null {
    try {
        const raw = localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : null;
    } catch {
        return null;
    }
}

function write(key: string, value: unknown): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // Quota exceeded or storage unavailable: the cache is only an optimisation.
    }
}

function remove(key: string): void {
    try {
        localStorage.removeItem(key);
    } catch {
        // Storage unavailable
    }
}

const conversationsKey = (userId: string | undefined) => `${CONVERSATIONS_PREFIX}${userId || 'anonymous'}`;

export const readConversations = (userId: string | undefined): ChatConversation[] => read<ChatConversation[]>(conversationsKey(userId)) ?? [];
export const writeConversations = (userId: string | undefined, list: ChatConversation[]): void => write(conversationsKey(userId), list);

export const readMessages = (conversationId: string): ChatMessageRecord[] | null => read<ChatMessageRecord[]>(`${MESSAGES_PREFIX}${conversationId}`);
export const writeMessages = (conversationId: string, messages: ChatMessageRecord[]): void => write(`${MESSAGES_PREFIX}${conversationId}`, messages);
export const removeMessages = (conversationId: string): void => remove(`${MESSAGES_PREFIX}${conversationId}`);

/** Cached chats must not outlive the session on a shared device. */
export function clearChatCache(): void {
    try {
        Object.keys(localStorage)
            .filter((key) => key.startsWith(CONVERSATIONS_PREFIX) || key.startsWith(MESSAGES_PREFIX))
            .forEach((key) => localStorage.removeItem(key));
    } catch {
        // Storage unavailable
    }
}
