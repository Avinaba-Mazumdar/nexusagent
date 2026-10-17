'use client';

import * as React from 'react';
import Link from 'next/link';
import Script from 'next/script';
import {
    Activity,
    Bot,
    Briefcase,
    ChevronDown,
    ChevronRight,
    Database,
    FileText,
    KeyRound,
    Loader2,
    LogIn,
    LogOut,
    MessageSquare,
    Moon,
    Plus,
    Send,
    Sparkles,
    Sun,
    Terminal,
    UploadCloud
} from 'lucide-react';
import { NexusLogo } from '@/components/icons';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { useAuthStore } from '@/lib/auth-store';
import { API_BASE, apiClient } from '@/lib/api-client';
import { HireMeModal } from '@/components/hire-me-modal';
import { ObservabilityPanel, type LogEntry, type TelemetryMetrics } from '@/components/observability-panel';
import { useAgentStream } from '@/hooks/useAgentStream';
import { MarkdownRenderer } from '@/components/canvas';
import { McpInspector } from '@/components/mcp';
import { ApprovalModal } from '@/components/approval';
import { SidebarChatHistory } from '@/components/sidebar';
import type { Citation, ChatMessageRecord, ChatConversation, ChatHistoryResponse, ChatConversationDetailResponse } from '@nexusagent/contracts';

interface ChatItem {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: Citation[];
}

interface SeededDoc {
    id: string;
    filename: string;
    total_chunks: number;
    uploaded_at?: string;
}

export default function Home() {
    const [prompt, setPrompt] = React.useState('');
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [popoverOpen, setPopoverOpen] = React.useState(false);
    const [isDarkTheme, setIsDarkTheme] = React.useState(false);
    const [, setGisLoaded] = React.useState(false);
    const [hireMeModalOpen, setHireMeModalOpen] = React.useState(false);
    const [seededDocs, setSeededDocs] = React.useState<SeededDoc[]>([]);
    const [messages, setMessages] = React.useState<ChatItem[]>([]);
    const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
    const [mobileActiveTab, setMobileActiveTab] = React.useState<'workspace' | 'chat' | 'observability'>('chat');
    const [selectedCitationDoc, setSelectedCitationDoc] = React.useState<string | null>(null);

    const [isObservabilityOpen, setIsObservabilityOpen] = React.useState(false);

    const [openCategories, setOpenCategories] = React.useState<{
        documents: boolean;
        chats: boolean;
        mcp: boolean;
    }>({
        documents: false,
        chats: true,
        mcp: false
    });

    const toggleCategory = React.useCallback((category: 'documents' | 'chats' | 'mcp') => {
        setOpenCategories((prev) => ({
            ...prev,
            [category]: !prev[category]
        }));
    }, []);

    const [metrics, setMetrics] = React.useState<TelemetryMetrics>({
        activeModel: 'gemini-2.5-flash',
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0,
        latencyMs: 0,
        rpmRemaining: 15,
        isByok: false
    });

    const [logs, setLogs] = React.useState<LogEntry[]>([
        {
            id: 'init-1',
            timestamp: new Date().toLocaleTimeString(),
            stage: 'ROUTER',
            message: 'Initialized model cascade gateway: gemini-2.5-flash primary (15 RPM ceiling)'
        },
        {
            id: 'init-2',
            timestamp: new Date().toLocaleTimeString(),
            stage: 'RAG',
            message: 'Connected Neon pgvector index (benchlm, openrouter, cursorbench)'
        }
    ]);

    const agentStream = useAgentStream({
        onLog: (entry) => setLogs((prev) => [...prev, entry]),
        onMetricUpdate: (updater) => setMetrics(updater)
    });

    const {
        user,
        token,
        quotaRemaining,
        bucketCapacity,
        isGuestLoading,
        isGoogleLoading,
        setIsGoogleLoading,
        error,
        byokKey,
        loginGuest,
        loginGoogle,
        logout,
        initAuth,
        setQuotaRemaining
    } = useAuthStore();

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
    const inFlightConversationsRef = React.useRef(false);
    const lastFetchConversationsRef = React.useRef<number>(0);
    const memoryMessageCache = React.useRef(new Map<string, ChatMessageRecord[]>());

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
                    try {
                        localStorage.setItem(storageKey, JSON.stringify(data.conversations));
                    } catch {
                        // Ignore quota
                    }

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
        [isGoogleUser, storageKey, prefetchMessages]
    );

    React.useEffect(() => {
        if (isGoogleUser) {
            loadConversations();
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
                    content: m.content
                }))
            );
        } else if (isLoading) {
            setMessages([]);
        }
    }, []);

    const handleNewChat = React.useCallback(() => {
        setActiveSessionId(null);
        setMessages([]);
    }, []);

    const handleSelectConversationItem = React.useCallback(
        (conv: ChatConversation) => {
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
        (e: React.MouseEvent, convId: string) => {
            e.stopPropagation();
            memoryMessageCache.current.delete(convId);

            setConversations((prev) => {
                const updated = prev.filter((c) => c.id !== convId);
                try {
                    localStorage.setItem(storageKey, JSON.stringify(updated));
                    localStorage.removeItem(`nexusagent_msgs_${convId}`);
                } catch {
                    // Ignore
                }
                return updated;
            });

            if (activeSessionId === convId) {
                handleNewChat();
            }

            apiClient(`/api/chat/history/${convId}`, { method: 'DELETE' }).catch(() => {
                // Background fail
            });
        },
        [storageKey, activeSessionId, handleNewChat]
    );

    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

    React.useEffect(() => {
        initAuth();
        if (typeof window !== 'undefined') {
            const storedTheme = localStorage.getItem('nexusagent_theme');
            const isDark = storedTheme === 'dark';
            setIsDarkTheme(isDark);
            if (isDark) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }

            if ((window as unknown as { google?: any })?.google) {
                setGisLoaded(true);
            }
        }
    }, [initAuth]);

    const handleToggleTheme = React.useCallback((checked?: boolean) => {
        setIsDarkTheme((prev) => {
            const next = typeof checked === 'boolean' ? checked : !prev;
            if (typeof document !== 'undefined') {
                if (next) {
                    document.documentElement.classList.add('dark');
                    localStorage.setItem('nexusagent_theme', 'dark');
                } else {
                    document.documentElement.classList.remove('dark');
                    localStorage.setItem('nexusagent_theme', 'light');
                }
            }
            return next;
        });
    }, []);

    // Fetch documents on mount and whenever authentication token changes
    const fetchDocs = React.useCallback(async () => {
        try {
            const endpoint = token ? `${API_BASE}/api/documents` : `${API_BASE}/api/chat/documents`;
            const headers: Record<string, string> = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(endpoint, { headers });
            if (res.ok) {
                const data = await res.json();
                if (data.documents) {
                    setSeededDocs(data.documents);
                    return;
                }
            }
        } catch {
            // Graceful fallback
        }
        setSeededDocs([
            { id: '1', filename: 'benchlm_evals.md', total_chunks: 5 },
            { id: '2', filename: 'cursor_bench.md', total_chunks: 4 },
            { id: '3', filename: 'openrouter_metrics.md', total_chunks: 5 },
            { id: '4', filename: 'leaks_rumours.md', total_chunks: 11 },
            { id: '5', filename: 'artificial_analysis.md', total_chunks: 4 }
        ]);
    }, [token]);

    React.useEffect(() => {
        fetchDocs();
    }, [fetchDocs]);

    const gsiInitializedRef = React.useRef(false);
    const handleCredentialRef = React.useRef<((credential: string) => Promise<void>) | null>(null);

    handleCredentialRef.current = async (credential: string) => {
        setIsGoogleLoading(true);
        const ok = await loginGoogle(credential);
        setIsGoogleLoading(false);
        if (ok) setDialogOpen(false);
    };

    const initGsi = React.useCallback(() => {
        if (gsiInitializedRef.current || !googleClientId) return;
        const google = (window as unknown as { google?: { accounts?: { id?: { initialize: Function; renderButton: Function } } } })?.google;
        if (!google?.accounts?.id) return;

        try {
            google.accounts.id.initialize({
                client_id: googleClientId,
                callback: (response: { credential?: string }) => {
                    if (response?.credential && handleCredentialRef.current) {
                        void handleCredentialRef.current(response.credential);
                    }
                }
            });
            gsiInitializedRef.current = true;
        } catch {
            // Graceful fallback
        }
    }, [googleClientId]);

    const renderGoogleButton = React.useCallback(
        (container: HTMLDivElement | null) => {
            if (!container || !googleClientId) return;
            const google = (window as unknown as { google?: { accounts?: { id?: { initialize: Function; renderButton: Function } } } })?.google;
            if (!google?.accounts?.id) return;

            initGsi();

            try {
                container.innerHTML = '';
                google.accounts.id.renderButton(container, {
                    theme: 'outline',
                    size: 'large',
                    width: 270,
                    text: 'signin_with',
                    shape: 'rectangular'
                });
            } catch {
                // Graceful fallback
            }
        },
        [googleClientId, initGsi]
    );

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const query = prompt.trim();
        if (!query || agentStream.isStreaming) return;

        // If user is not authenticated, open sign-in dialog and abort workflow
        if (!token) {
            setDialogOpen(true);
            return;
        }

        // Check if demo quota is exhausted and not BYOK
        if (!byokKey && quotaRemaining <= 0) {
            setHireMeModalOpen(true);
            return;
        }

        const userMsgId = `u-${Date.now()}`;
        const assistantMsgId = `a-${Date.now()}`;

        setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: query }, { id: assistantMsgId, role: 'assistant', content: '' }]);
        setPrompt('');

        // Decrement remaining quota if not BYOK
        if (!byokKey && quotaRemaining > 0) {
            setQuotaRemaining(quotaRemaining - 1);
        }

        try {
            const result = await agentStream.startStream({
                query,
                token,
                byokKey,
                sessionId: activeSessionId || undefined
            });

            const currentSessionId = result?.sessionId || activeSessionId;
            if (result?.sessionId && !activeSessionId) {
                setActiveSessionId(result.sessionId);
            }

            if (currentSessionId && isGoogleUser) {
                setConversations((prev) => {
                    const existing = prev.find((c) => c.id === currentSessionId);
                    const updatedItem: ChatConversation = existing
                        ? {
                              ...existing,
                              lastSnippet: query,
                              messageCount: (existing.messageCount || 0) + 2,
                              createdAt: new Date().toISOString()
                          }
                        : {
                              id: currentSessionId,
                              userId: user?.id || '',
                              title: query.slice(0, 45) + (query.length > 45 ? '...' : ''),
                              createdAt: new Date().toISOString(),
                              messageCount: 2,
                              lastSnippet: query
                          };
                    const filtered = prev.filter((c) => c.id !== currentSessionId);
                    const nextList = [updatedItem, ...filtered];
                    try {
                        localStorage.setItem(storageKey, JSON.stringify(nextList));
                    } catch {
                        // Ignore
                    }
                    return nextList;
                });
                void loadConversations(true);
            }

            if (result?.response) {
                setMessages((prev) => {
                    const next = prev.map((m) =>
                        m.id === assistantMsgId
                            ? {
                                  ...m,
                                  content: result.response,
                                  citations: result.citations
                              }
                            : m
                    );
                    if (currentSessionId && typeof window !== 'undefined') {
                        try {
                            localStorage.setItem(
                                `nexusagent_msgs_${currentSessionId}`,
                                JSON.stringify(
                                    next.map((m) => ({
                                        id: m.id,
                                        conversationId: currentSessionId,
                                        role: m.role,
                                        content: m.content,
                                        createdAt: new Date().toISOString()
                                    }))
                                )
                            );
                        } catch {
                            // Ignore
                        }
                    }
                    return next;
                });
            }
        } catch (err: unknown) {
            const errorText = err instanceof Error ? err.message : 'Failed to execute agent stream.';
            setMessages((prev) => prev.map((m) => (m.id === assistantMsgId ? { ...m, content: `Error: ${errorText}` } : m)));
        }
    };

    return (
        <div className="h-screen flex flex-col bg-background text-foreground font-sans overflow-hidden">
            <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onLoad={() => setGisLoaded(true)} />

            {/* 1. Header */}
            <header
                role="banner"
                aria-label="Command Center Navigation"
                className="h-14 bg-card border-b border-border px-4 md:px-6 flex items-center justify-between shrink-0 z-30"
            >
                <div className="flex items-center gap-3">
                    <NexusLogo className="h-8 w-8 rounded-xl shadow-xs shrink-0" aria-hidden="true" />
                    <div className="flex items-center gap-2">
                        <span className="font-heading font-bold text-sm tracking-tight text-foreground">NexusAgent</span>
                    </div>
                </div>

                <div className="flex items-center gap-2.5">
                    {/* Theme Toggle Button (Always accessible in header) */}
                    <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        onClick={() => handleToggleTheme()}
                        className="rounded-xl border-border h-9 w-9 text-muted-foreground hover:text-foreground shrink-0 cursor-pointer"
                        aria-label="Toggle theme mode"
                        title={isDarkTheme ? 'Switch to light mode' : 'Switch to dark mode'}
                    >
                        {isDarkTheme ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                    </Button>

                    {/* Observability Panel Toggle Button */}
                    <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        onClick={() => setIsObservabilityOpen((prev) => !prev)}
                        className={`relative rounded-xl border-border h-9 w-9 shrink-0 cursor-pointer transition-colors ${
                            isObservabilityOpen ? 'bg-secondary text-primary border-primary/40' : 'text-muted-foreground hover:text-foreground'
                        }`}
                        title={isObservabilityOpen ? 'Hide Observability Panel' : 'Show Observability Panel'}
                        aria-label="Toggle agent telemetry and observability panel"
                    >
                        <Activity className="h-4 w-4" aria-hidden="true" />
                        {agentStream.isStreaming && (
                            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-primary animate-pulse" />
                        )}
                    </Button>

                    {/* BYOK CTA Button */}
                    <Button
                        variant={byokKey ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setHireMeModalOpen(true)}
                        className={`text-xs font-semibold gap-1.5 rounded-xl border-border h-9 ${
                            byokKey ? 'bg-primary text-primary-foreground shadow-xs' : 'hover:bg-secondary'
                        }`}
                        title="Bring Your Own API Key"
                    >
                        <KeyRound className="h-3.5 w-3.5" />
                        <span>{byokKey ? 'BYOK Active' : 'Bring Your Own Key'}</span>
                    </Button>

                    {/* Pre-loaded Guest / User Quota Badge */}
                    {user && (
                        <div
                            className="hidden sm:flex items-center gap-1.5 h-9 px-3 rounded-xl bg-secondary/50 border border-border text-xs font-medium shrink-0"
                            title={`${quotaRemaining} of ${bucketCapacity} query quota remaining`}
                            data-testid="quota-badge"
                        >
                            <span className={`h-2 w-2 rounded-full shrink-0 ${quotaRemaining > 0 ? 'bg-success' : 'bg-destructive'}`} />
                            <span className="font-semibold text-foreground tabular-nums">
                                {quotaRemaining}/{bucketCapacity}
                            </span>
                            <span className="text-muted-foreground">{user.isGuest ? 'Free Pass' : 'Quota'}</span>
                        </div>
                    )}

                    {user ? (
                        <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
                            <PopoverTrigger asChild>
                                <button
                                    type="button"
                                    aria-label="User profile menu"
                                    className="group relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full p-0 border-0 bg-transparent cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                >
                                    <Avatar className="h-9 w-9 border border-border shadow-xs transition-colors duration-150 group-hover:border-primary group-hover:ring-2 group-hover:ring-primary/25">
                                        {user.avatarUrl ? <AvatarImage src={user.avatarUrl} alt={user.name} /> : null}
                                        <AvatarFallback className="bg-accent text-accent-foreground text-xs font-bold">
                                            {user.name
                                                ? user.name
                                                      .split(' ')
                                                      .map((n: string) => n[0])
                                                      .join('')
                                                      .slice(0, 2)
                                                      .toUpperCase()
                                                : 'U'}
                                        </AvatarFallback>
                                    </Avatar>
                                </button>
                            </PopoverTrigger>
                            <PopoverContent align="end" className="w-80 p-4 rounded-2xl shadow-xl border-border bg-popover text-popover-foreground">
                                {/* User Info */}
                                <div className="flex items-center gap-3 pb-3 border-b border-border">
                                    <Avatar className="h-10 w-10 border border-border shrink-0">
                                        {user.avatarUrl ? <AvatarImage src={user.avatarUrl} alt={user.name} /> : null}
                                        <AvatarFallback className="bg-accent text-accent-foreground text-sm font-bold">
                                            {user.name
                                                ? user.name
                                                      .split(' ')
                                                      .map((n: string) => n[0])
                                                      .join('')
                                                      .slice(0, 2)
                                                      .toUpperCase()
                                                : 'U'}
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="flex flex-col min-w-0 flex-1">
                                        <div className="flex items-center gap-1.5">
                                            <span className="font-heading font-bold text-sm text-foreground truncate">{user.name}</span>
                                            <Badge variant={user.isGuest ? 'outline' : 'soft'} className="text-[10px] px-1.5 py-0 font-medium shrink-0">
                                                {user.isGuest ? 'Guest' : 'Verified'}
                                            </Badge>
                                        </div>
                                        <span className="text-xs text-muted-foreground truncate" title={user.email || user.deviceId || user.id}>
                                            {user.email ? user.email : `Guest ID: ${(user.deviceId || user.id).slice(0, 12)}...`}
                                        </span>
                                    </div>
                                </div>

                                {/* Quota Section */}
                                <div className="py-3 border-b border-border space-y-1.5">
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="font-medium text-muted-foreground">API Quota</span>
                                        <span className="font-bold text-primary bg-accent px-2 py-0.5 rounded-md border border-border">
                                            {quotaRemaining}/{bucketCapacity} Quota
                                        </span>
                                    </div>
                                    <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden">
                                        <div
                                            className="bg-primary h-full rounded-full transition-all duration-300"
                                            style={{ width: `${Math.min(100, Math.max(0, (quotaRemaining / bucketCapacity) * 100))}%` }}
                                        />
                                    </div>
                                    <p className="text-[10px] text-muted-foreground">Hourly token replenishment enabled</p>
                                </div>

                                {/* Theme Switch */}
                                <div className="py-3 border-b border-border flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        {isDarkTheme ? (
                                            <Moon className="h-4 w-4 text-primary" aria-hidden="true" />
                                        ) : (
                                            <Sun className="h-4 w-4" aria-hidden="true" />
                                        )}
                                        <span className="text-xs font-medium text-foreground">Dark Mode</span>
                                    </div>
                                    <Switch checked={isDarkTheme} onCheckedChange={handleToggleTheme} aria-label="Toggle dark mode theme" />
                                </div>

                                {/* Legal & Policy Links */}
                                <div className="py-2.5 border-b border-border flex items-center justify-between text-[11px] text-muted-foreground px-0.5">
                                    <Link href="/privacy" className="hover:text-primary transition-colors">
                                        Privacy Policy
                                    </Link>
                                    <span>•</span>
                                    <Link href="/terms" className="hover:text-primary transition-colors">
                                        Terms of Service
                                    </Link>
                                </div>

                                {/* Sign Out */}
                                <div className="pt-3">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                            setPopoverOpen(false);
                                            logout();
                                        }}
                                        className="w-full justify-center gap-2 text-xs font-semibold text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive rounded-xl h-9"
                                    >
                                        <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                                        <span>Sign Out</span>
                                    </Button>
                                </div>
                            </PopoverContent>
                        </Popover>
                    ) : (
                        <div>
                            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button size="sm" variant="default" className="text-xs font-bold gap-1.5 rounded-xl h-9">
                                        <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                                        <span>Sign In</span>
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="sm:max-w-[480px] p-6 sm:p-7 rounded-3xl gap-4 border border-border/80 shadow-2xl">
                                    <DialogHeader className="text-left space-y-1">
                                        <DialogTitle className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-heading">
                                            Sign In to NexusAgent
                                        </DialogTitle>
                                        <DialogDescription className="text-xs sm:text-[13px] text-muted-foreground leading-relaxed">
                                            Choose an option to begin architecture analysis with your complimentary 5 live LLM quota balance.
                                        </DialogDescription>
                                    </DialogHeader>

                                    <div className="flex flex-col gap-4 pt-1">
                                        {/* Zero-Cost Mode Banner */}
                                        <div className="bg-banner-bg border border-banner-border rounded-2xl p-3 sm:p-3.5 flex items-center gap-3">
                                            <span className="shrink-0 bg-banner-badge-bg text-banner-badge-text text-[10px] font-mono font-bold tracking-wider px-2 py-1 rounded-md uppercase">
                                                ZERO-COST MODE
                                            </span>
                                            <p className="text-[11px] sm:text-xs text-muted-foreground leading-snug">
                                                All reasoning on NexusAgent is simulated or pre-cached for zero cloud bill. No real API keys required.
                                            </p>
                                        </div>

                                        {/* Sign In with Google Card (Prominent with purple border) */}
                                        <div className="border-2 border-featured-border rounded-2xl p-4 sm:p-5 bg-featured-bg relative">
                                            <h3 className="text-sm font-bold text-foreground">Sign in with Google</h3>
                                            <p className="text-xs text-muted-foreground mt-1 mb-4 leading-relaxed">
                                                Seamless one-click authentication. Never lose your architecture blueprints or execution traces.
                                            </p>

                                            <div className="relative w-full">
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    disabled={isGoogleLoading || isGuestLoading}
                                                    onClick={async () => {
                                                        setIsGoogleLoading(true);
                                                        const ok = await loginGoogle('mock-google-token:developer@nexusagent.internal:Lead Systems Architect');
                                                        setIsGoogleLoading(false);
                                                        if (ok) setDialogOpen(false);
                                                    }}
                                                    className="w-full justify-center gap-2.5 text-xs font-semibold border-border/80 hover:bg-secondary/70 rounded-xl h-11 shadow-xs bg-card text-foreground"
                                                    title="Continue with Google"
                                                >
                                                    {isGoogleLoading ? (
                                                        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
                                                    ) : (
                                                        <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                                                            <path
                                                                fill="#4285F4"
                                                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                                            />
                                                            <path
                                                                fill="#34A853"
                                                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                                            />
                                                            <path
                                                                fill="#FBBC05"
                                                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                                                            />
                                                            <path
                                                                fill="#EA4335"
                                                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                                                            />
                                                        </svg>
                                                    )}
                                                    <span>{isGoogleLoading ? 'Connecting...' : 'Continue with Google'}</span>
                                                </Button>

                                                {!isGoogleLoading && (
                                                    <div
                                                        ref={renderGoogleButton}
                                                        className="absolute inset-0 opacity-[0.001] cursor-pointer overflow-hidden rounded-xl flex items-center justify-center z-10"
                                                        title="Continue with Google"
                                                    />
                                                )}
                                            </div>
                                        </div>

                                        {/* Divider with OR */}
                                        <div className="relative flex items-center justify-center my-0.5">
                                            <div className="absolute inset-0 flex items-center">
                                                <div className="w-full border-t border-border/70" />
                                            </div>
                                            <div className="relative bg-card px-3 text-[10px] uppercase tracking-widest font-bold text-muted-foreground">
                                                OR
                                            </div>
                                        </div>

                                        {/* Continue as Guest Card */}
                                        <div className="bg-secondary/40 dark:bg-secondary/20 border border-border/70 rounded-2xl p-4 sm:p-5 flex items-center justify-between gap-4">
                                            <div className="space-y-1">
                                                <h3 className="text-sm font-bold text-foreground">Continue as Guest</h3>
                                                <p className="text-xs text-muted-foreground leading-relaxed max-w-[220px] sm:max-w-[260px]">
                                                    Immediate sandbox analysis. You will receive a 5 live LLM quota gift with zero registration required.
                                                </p>
                                            </div>
                                            <Button
                                                variant="outline"
                                                disabled={isGuestLoading || isGoogleLoading}
                                                onClick={async () => {
                                                    const ok = await loginGuest();
                                                    if (ok) setDialogOpen(false);
                                                }}
                                                className="shrink-0 bg-card hover:bg-secondary text-foreground font-semibold text-xs px-4 py-2.5 rounded-xl border-border/80 shadow-xs h-10"
                                            >
                                                {isGuestLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : 'Start as Guest'}
                                            </Button>
                                        </div>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground text-center pt-1">
                                        By continuing, you agree to our{' '}
                                        <Link href="/terms" onClick={() => setDialogOpen(false)} className="text-primary hover:underline">
                                            Terms &amp; Conditions
                                        </Link>{' '}
                                        and{' '}
                                        <Link href="/privacy" onClick={() => setDialogOpen(false)} className="text-primary hover:underline">
                                            Privacy Policy
                                        </Link>
                                        .
                                    </p>
                                    {error && <p className="text-[11px] text-destructive text-center pt-1">{error}</p>}
                                </DialogContent>
                            </Dialog>
                        </div>
                    )}
                </div>
            </header>

            {/* 4-Zone Body: Workspace (left) + Synthesis Canvas (center) + Observability (right) */}
            <div className="flex-1 flex overflow-hidden">
                {/* 2. Workspace Panel (Left) */}
                <aside
                    role="complementary"
                    aria-label="Workspace"
                    className={`w-full xl:w-72 2xl:w-80 bg-card border-r border-border flex flex-col shrink-0 h-full overflow-hidden ${
                        mobileActiveTab === 'workspace' ? 'flex' : 'hidden xl:flex'
                    }`}
                >
                    <div className="flex items-center justify-between p-3.5 pb-2.5 border-b border-border shrink-0">
                        <h2 className="flex items-center gap-1.5 text-xs font-heading font-bold text-foreground">
                            <Database className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                            <span>Workspace</span>
                        </h2>
                    </div>

                    <div className="flex-1 overflow-y-auto p-3 space-y-2.5 min-h-0">
                        {/* a. Documents Collapsible Category */}
                        <div className="rounded-xl border border-border/70 bg-card overflow-hidden shadow-2xs">
                            <button
                                type="button"
                                onClick={() => toggleCategory('documents')}
                                aria-expanded={openCategories.documents}
                                aria-controls="category-documents-content"
                                className="w-full h-10 px-3 flex items-center justify-between text-xs font-medium text-foreground hover:bg-secondary/50 transition-colors cursor-pointer select-none"
                            >
                                <div className="flex items-center gap-2">
                                    <FileText className="h-3.5 w-3.5 text-primary" />
                                    <span className="font-heading font-semibold text-xs text-foreground">Documents</span>
                                    <Badge variant="soft" className="text-[10px] font-mono py-0 px-1.5">
                                        {seededDocs.length}
                                    </Badge>
                                </div>
                                {openCategories.documents ? (
                                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                ) : (
                                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                                )}
                            </button>
                            {openCategories.documents && (
                                <div id="category-documents-content" className="p-3 pt-1 border-t border-border/50 space-y-2">
                                    <p className="text-[11px] text-muted-foreground">Pre-indexed AI benchmarks (Neon pgvector)</p>
                                    <div className="space-y-1.5 max-h-35 overflow-y-auto">
                                        {seededDocs.map((doc) => {
                                            const isSelected = Boolean(
                                                selectedCitationDoc && doc.filename.toLowerCase().includes(selectedCitationDoc.toLowerCase())
                                            );
                                            return (
                                                <div
                                                    key={doc.id}
                                                    className={`flex items-center justify-between p-2 rounded-lg border text-[11px] transition-all ${
                                                        isSelected
                                                            ? 'bg-primary/15 border-primary shadow-xs ring-1 ring-primary'
                                                            : 'bg-secondary/40 border-border/70'
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-1.5 truncate">
                                                        <FileText
                                                            className={`h-3.5 w-3.5 shrink-0 ${isSelected ? 'text-primary font-bold' : 'text-primary'}`}
                                                        />
                                                        <span className={`truncate font-mono ${isSelected ? 'text-primary font-bold' : 'text-foreground'}`}>
                                                            {doc.filename}
                                                        </span>
                                                    </div>
                                                    {isSelected ? (
                                                        <Badge variant="default" className="text-[9px] px-1 py-0 shrink-0 font-mono">
                                                            Source
                                                        </Badge>
                                                    ) : (
                                                        <Badge variant="outline" className="text-[9px] px-1 py-0 shrink-0">
                                                            {doc.total_chunks} chunks
                                                        </Badge>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>

                                    {/* Document Upload Button */}
                                    <Button
                                        variant="default"
                                        size="sm"
                                        onClick={() => setHireMeModalOpen(true)}
                                        className="w-full justify-center gap-1.5 text-xs font-bold rounded-xl mt-2 shadow-2xs h-9 cursor-pointer"
                                    >
                                        <UploadCloud className="h-3.5 w-3.5" />
                                        <span>Upload Markdown (.md)</span>
                                    </Button>

                                    {/* Lead Magnet Link */}
                                    <button
                                        type="button"
                                        onClick={() => setHireMeModalOpen(true)}
                                        className="w-full text-center text-[10px] text-muted-foreground hover:text-primary transition-colors cursor-pointer pt-0.5"
                                    >
                                        Need custom ETL pipelines? Inquire with author &rarr;
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* b. Chats Collapsible Category */}
                        <div className="rounded-xl border border-border/70 bg-card overflow-hidden shadow-2xs">
                            <button
                                type="button"
                                onClick={() => toggleCategory('chats')}
                                aria-expanded={openCategories.chats}
                                aria-controls="category-chats-content"
                                className="w-full h-10 px-3 flex items-center justify-between text-xs font-medium text-foreground hover:bg-secondary/50 transition-colors cursor-pointer select-none"
                            >
                                <div className="flex items-center gap-2">
                                    <MessageSquare className="h-3.5 w-3.5 text-primary" />
                                    <span className="font-heading font-semibold text-xs text-foreground">Chats</span>
                                    {isGoogleUser && conversations.length > 0 && (
                                        <Badge variant="soft" className="text-[10px] font-mono py-0 px-1.5">
                                            {conversations.length}
                                        </Badge>
                                    )}
                                </div>
                                {openCategories.chats ? (
                                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                ) : (
                                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                                )}
                            </button>

                            {openCategories.chats && (
                                <div id="category-chats-content" className="p-2.5 pt-1 border-t border-border/50">
                                    <SidebarChatHistory
                                        isGoogleUser={isGoogleUser}
                                        activeSessionId={activeSessionId}
                                        conversations={conversations}
                                        isLoading={isLoadingConversations}
                                        searchQuery={chatSearchQuery}
                                        onSearchChange={setChatSearchQuery}
                                        onSelectConversation={handleSelectConversationItem}
                                        onDeleteConversation={handleDeleteConversation}
                                        onPrefetchConversation={prefetchMessages}
                                        onOpenSignIn={() => setDialogOpen(true)}
                                    />
                                </div>
                            )}
                        </div>

                        {/* c. MCP Collapsible Category */}
                        <div className="rounded-xl border border-border/70 bg-card overflow-hidden shadow-2xs">
                            <button
                                type="button"
                                onClick={() => toggleCategory('mcp')}
                                aria-expanded={openCategories.mcp}
                                aria-controls="category-mcp-content"
                                className="w-full h-10 px-3 flex items-center justify-between text-xs font-medium text-foreground hover:bg-secondary/50 transition-colors cursor-pointer select-none"
                            >
                                <div className="flex items-center gap-2">
                                    <Terminal className="h-3.5 w-3.5 text-primary" />
                                    <span className="font-heading font-semibold text-xs text-foreground">MCP Protocol</span>
                                    <Badge variant="soft" className="text-[9px] font-mono py-0 px-1.5">
                                        v2
                                    </Badge>
                                </div>
                                {openCategories.mcp ? (
                                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                ) : (
                                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                                )}
                            </button>
                            {openCategories.mcp && (
                                <div id="category-mcp-content" className="p-1 pt-0 border-t border-border/50">
                                    <McpInspector apiBase={API_BASE} authToken={token} />
                                </div>
                            )}
                        </div>
                    </div>

                    {/* d. Bottom Footer (always on bottom) */}
                    <div className="shrink-0 p-3 border-t border-border bg-card/80 text-[11px] text-muted-foreground flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Link href="/privacy" className="hover:text-primary transition-colors">
                                Privacy Policy
                            </Link>
                            <span>•</span>
                            <Link href="/terms" className="hover:text-primary transition-colors">
                                Terms
                            </Link>
                        </div>
                        <span className="font-mono text-[10px] text-muted-foreground/75">nexusagent.avinaba.com</span>
                    </div>
                </aside>

                {/* 3. Active Chat Canvas (Center) */}
                <main
                    role="main"
                    aria-label="Active Chat Canvas"
                    className={`relative flex-1 flex-col overflow-hidden bg-background ${mobileActiveTab === 'chat' ? 'flex' : 'hidden xl:flex'}`}
                >
                    {/* Floating New Chat Action Button */}
                    <div className="absolute top-4 right-4 z-20">
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleNewChat}
                            title="Start New Chat"
                            aria-label="New Chat"
                            className="h-9 px-3 rounded-xl border border-border/80 bg-card/90 hover:bg-secondary text-foreground shadow-sm backdrop-blur-xs flex items-center gap-1.5 font-medium text-xs cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
                        >
                            <Plus className="h-3.5 w-3.5 text-primary" />
                            <span>New Chat</span>
                        </Button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
                        {/* Quota Depleted Lead Magnet Alert */}
                        {!byokKey && quotaRemaining <= 0 && (
                            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                                <div>
                                    <p className="font-bold text-foreground">Demo Token Quota Reached</p>
                                    <p className="text-muted-foreground text-[11px] mt-0.5">
                                        Use your own API key to continue querying without limits, or book a custom architecture build.
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => setHireMeModalOpen(true)}
                                        className="text-xs font-semibold rounded-xl h-8 gap-1 cursor-pointer"
                                    >
                                        <KeyRound className="h-3.5 w-3.5" />
                                        <span>Use My Key</span>
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="default"
                                        onClick={() => setHireMeModalOpen(true)}
                                        className="text-xs font-bold rounded-xl h-8 gap-1"
                                    >
                                        <Briefcase className="h-3.5 w-3.5" />
                                        <span>Hire Me</span>
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Messages Thread */}
                        {messages.length === 0 ? (
                            <Card className="shadow-xs border-border">
                                <CardHeader className="p-4 pb-2">
                                    <CardTitle className="text-sm font-heading font-bold text-foreground flex items-center gap-2">
                                        <Sparkles className="h-4 w-4 text-primary" />
                                        Autonomous Systems Intelligence
                                    </CardTitle>
                                    <CardDescription className="text-xs text-muted-foreground">
                                        RAG-augmented reasoning against weekly AI model benchmarks (BenchLM, OpenRouter, CursorBench).
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="p-4 pt-2 space-y-3">
                                    <div className="p-3.5 rounded-xl bg-secondary/40 border border-border text-xs text-muted-foreground leading-relaxed">
                                        Ask benchmark comparisons, context lengths, token costs, or agentic coding leaderboard rankings.
                                    </div>
                                    <div className="flex flex-wrap gap-2 pt-1">
                                        {[
                                            'Compare Claude Sonnet 3.7 vs GPT-4o on CursorBench coding benchmarks',
                                            'Which models have the lowest input token cost per 1M on OpenRouter?',
                                            'Summarize BenchLM coding leaderboard rankings and pass rates',
                                            'Compare context window lengths across top Gemini, Claude, and OpenAI models'
                                        ].map((promptText) => (
                                            <button
                                                key={promptText}
                                                type="button"
                                                onClick={() => setPrompt(promptText)}
                                                className="text-[11px] px-3 py-1.5 rounded-lg border border-border/80 bg-card hover:bg-secondary text-foreground text-left transition-colors cursor-pointer"
                                            >
                                                &ldquo;{promptText}&rdquo;
                                            </button>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="space-y-4">
                                {messages.map((msg) => (
                                    <div key={msg.id} className={`flex gap-3 text-xs leading-relaxed ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        {msg.role === 'assistant' && (
                                            <div className="h-7 w-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 mt-0.5">
                                                <Bot className="h-4 w-4" />
                                            </div>
                                        )}
                                        <div
                                            className={`p-3.5 rounded-2xl ${
                                                msg.role === 'user'
                                                    ? 'max-w-2xl bg-primary text-primary-foreground font-medium rounded-tr-xs whitespace-pre-wrap'
                                                    : 'max-w-3xl xl:max-w-4xl bg-card border border-border text-foreground shadow-2xs rounded-tl-xs w-full'
                                            }`}
                                        >
                                            {msg.role === 'user' ? (
                                                msg.content
                                            ) : msg.content ? (
                                                <MarkdownRenderer
                                                    content={msg.content}
                                                    citations={msg.citations}
                                                    isDark={isDarkTheme}
                                                    onCitationClick={(cite) => setSelectedCitationDoc(cite.filename)}
                                                />
                                            ) : agentStream.isStreaming && msg.id === messages[messages.length - 1]?.id ? (
                                                agentStream.streamedResponse ? (
                                                    <MarkdownRenderer
                                                        content={agentStream.streamedResponse}
                                                        isStreaming={true}
                                                        citations={agentStream.citations}
                                                        isDark={isDarkTheme}
                                                        onCitationClick={(cite) => setSelectedCitationDoc(cite.filename)}
                                                    />
                                                ) : (
                                                    <div className="flex items-center gap-1.5 text-muted-foreground">
                                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                        <span>Executing DAG [{agentStream.currentNode?.toUpperCase() || 'PLANNER'}]...</span>
                                                    </div>
                                                )
                                            ) : (
                                                <div className="flex items-center gap-1.5 text-muted-foreground">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    <span>Synthesizing response...</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Chat Input Form */}
                    <form onSubmit={handleSubmit} role="search" aria-label="Architecture inquiry input" className="p-4 bg-card border-t border-border shrink-0">
                        <div className="relative flex items-center">
                            <Input
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="Ask architectural question or query benchmark knowledge base..."
                                disabled={agentStream.isStreaming}
                                className="pr-24 min-h-11 text-xs rounded-xl bg-secondary/40 border-border text-foreground focus-visible:bg-card"
                            />
                            <Button
                                type="submit"
                                size="sm"
                                variant="default"
                                disabled={agentStream.isStreaming || !prompt.trim()}
                                aria-label="Send query"
                                className="absolute right-1.5 top-1/2 -translate-y-1/2 h-8 px-4 text-xs rounded-lg gap-1.5 font-bold"
                            >
                                {agentStream.isStreaming ? (
                                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                                ) : (
                                    <>
                                        <span>Send</span>
                                        <Send className="h-3 w-3" aria-hidden="true" />
                                    </>
                                )}
                            </Button>
                        </div>
                    </form>
                </main>

                {/* 4. Observability Panel (Right) */}
                <ObservabilityPanel
                    metrics={metrics}
                    logs={logs}
                    currentNode={agentStream.currentNode}
                    plan={agentStream.plan}
                    reflectionScore={agentStream.reflectionScore}
                    isStreaming={agentStream.isStreaming}
                    isOpen={isObservabilityOpen}
                    onClose={() => setIsObservabilityOpen(false)}
                    className={
                        mobileActiveTab === 'observability'
                            ? 'flex'
                            : isObservabilityOpen
                              ? 'hidden xl:flex'
                              : 'hidden'
                    }
                />
            </div>

            {/* Mobile Bottom Navigation */}
            <div className="xl:hidden flex items-center justify-around bg-card border-t border-border p-2 shrink-0 z-40 pb-safe">
                <button
                    onClick={() => setMobileActiveTab('workspace')}
                    className={`flex flex-col items-center p-2 rounded-lg min-w-[70px] ${
                        mobileActiveTab === 'workspace' ? 'text-primary bg-primary/10 font-bold' : 'text-muted-foreground hover:bg-secondary/50 font-medium'
                    }`}
                >
                    <Database className="h-5 w-5" />
                    <span className="text-[10px] mt-1">Workspace</span>
                </button>
                <button
                    onClick={() => setMobileActiveTab('chat')}
                    className={`flex flex-col items-center p-2 rounded-lg min-w-[70px] ${
                        mobileActiveTab === 'chat' ? 'text-primary bg-primary/10 font-bold' : 'text-muted-foreground hover:bg-secondary/50 font-medium'
                    }`}
                >
                    <MessageSquare className="h-5 w-5" />
                    <span className="text-[10px] mt-1">Canvas</span>
                </button>
                <button
                    onClick={() => setMobileActiveTab('observability')}
                    className={`flex flex-col items-center p-2 rounded-lg min-w-[70px] ${
                        mobileActiveTab === 'observability' ? 'text-primary bg-primary/10 font-bold' : 'text-muted-foreground hover:bg-secondary/50 font-medium'
                    }`}
                >
                    <Activity className="h-5 w-5" />
                    <span className="text-[10px] mt-1">Observe</span>
                </button>
            </div>

            {/* Modals */}
            <HireMeModal open={hireMeModalOpen} onOpenChange={setHireMeModalOpen} />
            <ApprovalModal open={Boolean(agentStream.pendingApproval)} approval={agentStream.pendingApproval} onResolve={agentStream.resolveApproval} />
        </div>
    );
}
