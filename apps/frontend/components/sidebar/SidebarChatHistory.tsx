'use client';

import * as React from 'react';
import { Check, Clock, Loader2, LogIn, MessageSquare, Search, Trash2, X } from 'lucide-react';
import type { ChatConversation } from '@nexusagent/contracts';
import { Button } from '@/components/ui/button';

export interface SidebarChatHistoryProps {
    isGoogleUser: boolean;
    activeSessionId?: string | null;
    conversations: ChatConversation[];
    isLoading: boolean;
    searchQuery: string;
    onSearchChange: (query: string) => void;
    onSelectConversation: (conv: ChatConversation) => void;
    onDeleteConversation: (convId: string) => void;
    onPrefetchConversation?: (convId: string) => void;
    onOpenSignIn: () => void;
}

function formatRelativeTime(dateString: string): string {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
        return '';
    }
}

function getGroupLabel(dateString: string): 'Today' | 'Yesterday' | 'Previous 7 Days' | 'Older' {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        const itemTime = date.getTime();

        if (itemTime >= todayStart) return 'Today';
        if (itemTime >= todayStart - 86400000) return 'Yesterday';
        if (itemTime >= todayStart - 7 * 86400000) return 'Previous 7 Days';
        return 'Older';
    } catch {
        return 'Older';
    }
}

export function SidebarChatHistory({
    isGoogleUser,
    activeSessionId,
    conversations,
    isLoading,
    searchQuery,
    onSearchChange,
    onSelectConversation,
    onDeleteConversation,
    onPrefetchConversation,
    onOpenSignIn
}: SidebarChatHistoryProps) {
    // Two-step delete: the first click arms a confirm button that disarms itself after a few seconds.
    const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);

    React.useEffect(() => {
        if (!pendingDeleteId) return;
        const timeout = setTimeout(() => setPendingDeleteId(null), 4000);
        return () => clearTimeout(timeout);
    }, [pendingDeleteId]);

    const filteredConversations = React.useMemo(() => {
        const query = searchQuery.trim().toLowerCase();
        if (!query) return conversations;
        return conversations.filter((c) => c.title.toLowerCase().includes(query) || (c.lastSnippet && c.lastSnippet.toLowerCase().includes(query)));
    }, [conversations, searchQuery]);

    const groupedConversations = React.useMemo(() => {
        const groups: Record<string, ChatConversation[]> = {
            Today: [],
            Yesterday: [],
            'Previous 7 Days': [],
            Older: []
        };

        for (const conv of filteredConversations) {
            const group = getGroupLabel(conv.updatedAt || conv.createdAt);
            groups[group].push(conv);
        }

        return groups;
    }, [filteredConversations]);

    if (!isGoogleUser) {
        return (
            <div className="p-3 text-center space-y-2 bg-secondary/30 rounded-lg border border-border/60">
                <MessageSquare className="h-5 w-5 text-muted-foreground/60 mx-auto" />
                <div className="space-y-0.5">
                    <p className="text-[11px] font-medium text-foreground">Sign in to save chat history</p>
                    <p className="text-[10px] text-muted-foreground leading-snug">Conversations are synced securely with your Google account.</p>
                </div>
                <Button size="sm" variant="outline" onClick={onOpenSignIn} className="w-full text-xs font-semibold h-7 rounded-lg gap-1.5 cursor-pointer mt-1">
                    <LogIn className="h-3 w-3" />
                    <span>Sign In with Google</span>
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {/* Search Input */}
            <div className="relative flex items-center">
                <Search className="absolute left-2.5 h-3 w-3 text-muted-foreground pointer-events-none" />
                <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder="Search chats..."
                    aria-label="Search conversation history"
                    className="w-full h-7 pl-7 pr-6 text-[11px] rounded-lg border border-border bg-secondary/40 text-foreground placeholder:text-muted-foreground focus:outline-hidden focus:ring-1 focus:ring-primary"
                />
                {searchQuery && (
                    <button
                        type="button"
                        onClick={() => onSearchChange('')}
                        aria-label="Clear search query"
                        className="absolute right-1.5 text-muted-foreground hover:text-foreground p-0.5 rounded cursor-pointer"
                    >
                        <X className="h-3 w-3" />
                    </button>
                )}
            </div>

            {/* Conversation List */}
            <div className="space-y-2 max-h-56 overflow-y-auto pr-0.5">
                {isLoading && conversations.length === 0 ? (
                    <div className="flex items-center justify-center py-6 text-muted-foreground text-xs gap-1.5">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                        <span className="text-[11px]">Loading chats...</span>
                    </div>
                ) : filteredConversations.length === 0 ? (
                    <div className="py-6 px-2 text-center text-muted-foreground text-[11px] space-y-1">
                        <MessageSquare className="h-5 w-5 mx-auto opacity-30" />
                        <p className="font-semibold text-foreground text-xs">{searchQuery ? 'No matching chats' : 'No history yet'}</p>
                        <p className="text-[10px] leading-relaxed">
                            {searchQuery ? 'Try adjusting your search keywords.' : 'Send a prompt on the Chat Canvas to start.'}
                        </p>
                    </div>
                ) : (
                    (['Today', 'Yesterday', 'Previous 7 Days', 'Older'] as const).map((groupKey) => {
                        const items = groupedConversations[groupKey];
                        if (!items || items.length === 0) return null;

                        return (
                            <div key={groupKey} className="space-y-0.5">
                                <span className="block px-1 text-[10px] font-bold text-muted-foreground tracking-wider uppercase">{groupKey}</span>
                                <div className="space-y-0.5">
                                    {items.map((conv) => {
                                        const isActive = activeSessionId === conv.id;
                                        const isConfirming = pendingDeleteId === conv.id;
                                        return (
                                            <div
                                                key={conv.id}
                                                className={`group w-full px-2 py-1.5 rounded-lg text-xs flex items-center justify-between gap-1.5 transition-colors ${
                                                    isActive
                                                        ? 'bg-primary/15 border border-primary/40 text-foreground font-medium'
                                                        : 'hover:bg-secondary/60 text-foreground/90 border border-transparent'
                                                }`}
                                            >
                                                <button
                                                    type="button"
                                                    onMouseEnter={() => onPrefetchConversation?.(conv.id)}
                                                    onFocus={() => onPrefetchConversation?.(conv.id)}
                                                    onClick={() => onSelectConversation(conv)}
                                                    aria-current={isActive ? 'true' : undefined}
                                                    className="min-w-0 flex-1 text-left cursor-pointer rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                                                >
                                                    <p
                                                        className={`truncate text-[11px] ${
                                                            isActive
                                                                ? 'font-semibold text-primary'
                                                                : 'text-foreground group-hover:text-primary transition-colors'
                                                        }`}
                                                    >
                                                        {conv.title}
                                                    </p>
                                                    <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                                                        <Clock className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
                                                        <span>{formatRelativeTime(conv.updatedAt || conv.createdAt)}</span>
                                                        {conv.messageCount && conv.messageCount > 0 ? (
                                                            <>
                                                                <span aria-hidden="true">•</span>
                                                                <span>{conv.messageCount} msgs</span>
                                                            </>
                                                        ) : null}
                                                    </span>
                                                </button>

                                                {isConfirming ? (
                                                    <div className="flex items-center gap-0.5 shrink-0">
                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                setPendingDeleteId(null);
                                                                onDeleteConversation(conv.id);
                                                            }}
                                                            aria-label={`Confirm delete ${conv.title}`}
                                                            className="flex items-center gap-0.5 px-1.5 py-1 rounded bg-destructive text-destructive-foreground text-[10px] font-semibold cursor-pointer"
                                                        >
                                                            <Check className="h-3 w-3" aria-hidden="true" />
                                                            Delete
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={() => setPendingDeleteId(null)}
                                                            aria-label="Cancel delete"
                                                            className="p-1 rounded text-muted-foreground hover:bg-secondary cursor-pointer"
                                                        >
                                                            <X className="h-3 w-3" aria-hidden="true" />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        onClick={() => setPendingDeleteId(conv.id)}
                                                        aria-label={`Delete conversation ${conv.title}`}
                                                        title="Delete conversation"
                                                        className="p-1 rounded hover:bg-destructive/10 hover:text-destructive text-muted-foreground transition-all shrink-0 cursor-pointer opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:group-focus-within:opacity-100"
                                                    >
                                                        <Trash2 className="h-3 w-3" aria-hidden="true" />
                                                    </button>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
