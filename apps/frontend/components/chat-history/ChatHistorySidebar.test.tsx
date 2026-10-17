import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SidebarChatHistory } from '@/components/sidebar/SidebarChatHistory';

describe('SidebarChatHistory Component', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it('shows sign-in prompt when isGoogleUser is false', () => {
        render(
            <SidebarChatHistory
                isGoogleUser={false}
                conversations={[]}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={vi.fn()}
            />
        );
        expect(screen.getByText('Sign in to save chat history')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
    });

    it('calls onOpenSignIn when clicking sign in button in guest state', async () => {
        const user = userEvent.setup();
        const handleSignIn = vi.fn();
        render(
            <SidebarChatHistory
                isGoogleUser={false}
                conversations={[]}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={handleSignIn}
            />
        );

        await user.click(screen.getByRole('button', { name: /sign in with google/i }));
        expect(handleSignIn).toHaveBeenCalledTimes(1);
    });

    it('renders search input and conversation list when isGoogleUser is true', () => {
        const mockConversations = [
            {
                id: 'c1',
                userId: 'user-123',
                title: 'Raft Consensus Protocol Verification',
                createdAt: new Date().toISOString()
            }
        ];

        render(
            <SidebarChatHistory
                isGoogleUser={true}
                conversations={mockConversations}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={vi.fn()}
            />
        );

        expect(screen.getByRole('searchbox', { name: /search conversation history/i })).toBeInTheDocument();
        expect(screen.getByText('Raft Consensus Protocol Verification')).toBeInTheDocument();
    });

    it('filters conversations by search query', () => {
        const mockConversations = [
            {
                id: 'c1',
                userId: 'user-123',
                title: 'Raft Consensus Protocol Verification',
                createdAt: new Date().toISOString()
            },
            {
                id: 'c2',
                userId: 'user-123',
                title: 'PostgreSQL Vector Search Indexing',
                createdAt: new Date().toISOString()
            }
        ];

        const { rerender } = render(
            <SidebarChatHistory
                isGoogleUser={true}
                conversations={mockConversations}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={vi.fn()}
            />
        );

        expect(screen.getByText('Raft Consensus Protocol Verification')).toBeInTheDocument();
        expect(screen.getByText('PostgreSQL Vector Search Indexing')).toBeInTheDocument();

        rerender(
            <SidebarChatHistory
                isGoogleUser={true}
                conversations={mockConversations}
                isLoading={false}
                searchQuery="Raft"
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={vi.fn()}
            />
        );

        expect(screen.getByText('Raft Consensus Protocol Verification')).toBeInTheDocument();
        expect(screen.queryByText('PostgreSQL Vector Search Indexing')).not.toBeInTheDocument();
    });

    it('triggers onSelectConversation when clicking a conversation item', async () => {
        const user = userEvent.setup();
        const handleSelect = vi.fn();
        const conv = {
            id: 'c1',
            userId: 'user-123',
            title: 'Neural Architecture Search',
            createdAt: new Date().toISOString()
        };

        render(
            <SidebarChatHistory
                isGoogleUser={true}
                conversations={[conv]}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={handleSelect}
                onDeleteConversation={vi.fn()}
                onOpenSignIn={vi.fn()}
            />
        );

        await user.click(screen.getByText('Neural Architecture Search'));
        expect(handleSelect).toHaveBeenCalledWith(conv);
    });

    it('triggers onDeleteConversation when clicking delete button', async () => {
        const user = userEvent.setup();
        const handleDelete = vi.fn();
        const conv = {
            id: 'c1',
            userId: 'user-123',
            title: 'Neural Architecture Search',
            createdAt: new Date().toISOString()
        };

        render(
            <SidebarChatHistory
                isGoogleUser={true}
                conversations={[conv]}
                isLoading={false}
                searchQuery=""
                onSearchChange={vi.fn()}
                onSelectConversation={vi.fn()}
                onDeleteConversation={handleDelete}
                onOpenSignIn={vi.fn()}
            />
        );

        const deleteBtn = screen.getByRole('button', { name: /delete conversation/i });
        await user.click(deleteBtn);
        expect(handleDelete).toHaveBeenCalledTimes(1);
    });
});
