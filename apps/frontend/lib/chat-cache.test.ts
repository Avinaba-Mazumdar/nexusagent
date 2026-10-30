import { beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import type { ChatConversation, ChatMessageRecord } from '@nexusagent/contracts';
import { clearChatCache, readConversations, readMessages, removeMessages, writeConversations, writeMessages } from './chat-cache';

const conversation = { id: 'c1', userId: 'u1', title: 'T', createdAt: '2026-01-01T00:00:00Z' } as ChatConversation;
const message = { id: 'm1', conversationId: 'c1', role: 'user', content: 'hi', createdAt: '2026-01-01T00:00:00Z' } as ChatMessageRecord;

describe('chat-cache', () => {
    beforeEach(() => localStorage.clear());

    it('round-trips conversations per user and messages per conversation', () => {
        writeConversations('u1', [conversation]);
        writeMessages('c1', [message]);

        expect(readConversations('u1')).toEqual([conversation]);
        expect(readConversations('u2')).toEqual([]);
        expect(readMessages('c1')).toEqual([message]);

        removeMessages('c1');
        expect(readMessages('c1')).toBeNull();
    });

    it('clearChatCache removes chats but leaves other keys', () => {
        writeConversations('u1', [conversation]);
        writeMessages('c1', [message]);
        localStorage.setItem('nexusagent_theme', 'dark');

        clearChatCache();

        expect(readConversations('u1')).toEqual([]);
        expect(readMessages('c1')).toBeNull();
        expect(localStorage.getItem('nexusagent_theme')).toBe('dark');
    });

    it('never throws when storage is unavailable or corrupt', () => {
        localStorage.setItem('nexusagent_msgs_c1', '{not json');
        expect(readMessages('c1')).toBeNull();

        const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('quota');
        });
        expect(() => writeMessages('c1', [message])).not.toThrow();
        setItem.mockRestore();
    });
});
