'use client';

import * as React from 'react';
import Script from 'next/script';
import { Activity, Database, MessageSquare } from 'lucide-react';
import { useAuthStore } from '@/lib/auth-store';
import { API_BASE } from '@/lib/api-client';
import { HireMeModal } from '@/components/hire-me-modal';
import { ObservabilityPanel, type LogEntry, type TelemetryMetrics } from '@/components/observability-panel';
import { AgentStreamError, useAgentStream } from '@/hooks/useAgentStream';
import { AppHeader } from '@/components/app-header';
import { SignInDialog } from '@/components/sign-in-dialog';
import { WorkspaceSidebar, type WorkspaceDoc, type UploadState } from '@/components/workspace-sidebar';
import { ChatCanvas } from '@/components/chat-canvas';
import { Composer } from '@/components/composer';
import { useChatHistory, type ChatItem } from '@/hooks/useChatHistory';
import type { ChatConversation } from '@nexusagent/contracts';

const MAX_LOG_ENTRIES = 200;
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
const XL_BREAKPOINT_QUERY = '(min-width: 1280px)';

function normalizeDoc(raw: Record<string, unknown>): WorkspaceDoc {
    return {
        id: String(raw.id),
        filename: String(raw.filename),
        totalChunks: Number(raw.totalChunks ?? raw.total_chunks ?? 0),
        isSeeded: Boolean(raw.isSeeded ?? raw.is_seeded ?? true)
    };
}

export default function Home() {
    const [prompt, setPrompt] = React.useState('');
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [isDarkTheme, setIsDarkTheme] = React.useState(false);
    const [gisLoaded, setGisLoaded] = React.useState(false);
    const [hireMeModalOpen, setHireMeModalOpen] = React.useState(false);
    const [docs, setDocs] = React.useState<WorkspaceDoc[]>([]);
    const [docsError, setDocsError] = React.useState<string | null>(null);
    const [uploadState, setUploadState] = React.useState<UploadState>({ status: 'idle' });
    const [streamingMsgId, setStreamingMsgId] = React.useState<string | null>(null);
    const [liveStatus, setLiveStatus] = React.useState('');
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

    const [metrics, setMetrics] = React.useState<TelemetryMetrics>({ firstTokenMs: null, totalLatencyMs: null, iterationCount: null });
    const [logs, setLogs] = React.useState<LogEntry[]>([]);

    const {
        user,
        token,
        quotaRemaining,
        bucketCapacity,
        isGuestLoading,
        isGoogleLoading,
        setIsGoogleLoading,
        error,
        loginGuest,
        loginGoogle,
        logout,
        initAuth,
        setQuotaRemaining
    } = useAuthStore();

    const isGoogleUser = Boolean(user && !user.isGuest);

    const {
        conversations,
        setConversations,
        isLoadingConversations,
        chatSearchQuery,
        setChatSearchQuery,
        chatNotice,
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
    } = useChatHistory(user);

    const agentStream = useAgentStream({
        onLog: (entry) => setLogs((prev) => [...prev, entry].slice(-MAX_LOG_ENTRIES)),
        onMetricUpdate: (updater) => setMetrics(updater),
        onQuota: (remaining) => setQuotaRemaining(remaining)
    });

    const streamedResponseRef = React.useRef('');
    streamedResponseRef.current = agentStream.streamedResponse;

    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

    React.useEffect(() => {
        initAuth();
        setIsDarkTheme(document.documentElement.classList.contains('dark'));
        if ((window as unknown as { google?: unknown }).google) {
            setGisLoaded(true);
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

    const fetchDocs = React.useCallback(async () => {
        try {
            const endpoint = token ? `${API_BASE}/api/documents` : `${API_BASE}/api/chat/documents`;
            const headers: Record<string, string> = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(endpoint, { headers });
            if (res.ok) {
                const data = await res.json();
                if (Array.isArray(data.documents)) {
                    setDocs(data.documents.map(normalizeDoc));
                    setDocsError(null);
                    return;
                }
            }
        } catch {
            // Reported below
        }
        setDocsError("Couldn't load the document list.");
    }, [token]);

    React.useEffect(() => {
        fetchDocs();
    }, [fetchDocs]);

    const fileInputRef = React.useRef<HTMLInputElement>(null);

    const handleUploadClick = () => {
        if (!token) {
            setDialogOpen(true);
            return;
        }
        fileInputRef.current?.click();
    };

    const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file || !token) return;
        if (file.size > MAX_UPLOAD_BYTES) {
            setUploadState({ status: 'error', message: 'File is larger than the 5 MB limit.' });
            return;
        }

        setUploadState({ status: 'uploading', message: `Indexing ${file.name}…` });
        const body = new FormData();
        body.append('file', file);
        try {
            const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
            const res = await fetch(`${API_BASE}/api/documents/upload`, { method: 'POST', headers, body });
            const data = await res.json().catch(() => null);
            if (!res.ok) {
                const detail = typeof data?.detail === 'string' ? data.detail : `Upload failed (HTTP ${res.status}).`;
                throw new Error(res.status === 429 ? 'Quota exhausted. Each upload uses one query.' : detail);
            }
            setUploadState({
                status: 'success',
                message: `Indexed ${data?.document?.filename ?? file.name} (${data?.chunksCount ?? 0} chunks).`
            });
            setQuotaRemaining(Math.max(0, quotaRemaining - 1));
            void fetchDocs();
        } catch (err) {
            setUploadState({ status: 'error', message: err instanceof Error ? err.message : 'Upload failed.' });
        }
    };

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
            if (!container || !googleClientId || !gisLoaded) return;
            const google = (window as unknown as { google?: { accounts?: { id?: { initialize: Function; renderButton: Function } } } })?.google;
            if (!google?.accounts?.id) return;

            initGsi();

            try {
                container.innerHTML = '';
                google.accounts.id.renderButton(container, {
                    theme: isDarkTheme ? 'filled_black' : 'outline',
                    size: 'large',
                    width: Math.round(Math.min(400, Math.max(200, container.offsetWidth || 320))),
                    text: 'continue_with',
                    shape: 'rectangular',
                    logo_alignment: 'center'
                });
            } catch {
                // Graceful fallback
            }
        },
        [googleClientId, gisLoaded, initGsi, isDarkTheme]
    );

    const handleCitationClick = React.useCallback((cite: { filename: string }) => {
        setSelectedCitationDoc(cite.filename);
        setOpenCategories((prev) => ({ ...prev, documents: true }));
        if (typeof window !== 'undefined' && !window.matchMedia?.(XL_BREAKPOINT_QUERY).matches) {
            setMobileActiveTab('workspace');
        }
    }, []);

    React.useEffect(() => {
        if (!selectedCitationDoc) return;
        const frame = requestAnimationFrame(() => {
            document.querySelector('[data-selected-doc="true"]')?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
        });
        return () => cancelAnimationFrame(frame);
    }, [selectedCitationDoc, openCategories.documents, mobileActiveTab]);

    const scrollContainerRef = React.useRef<HTMLDivElement>(null);
    const stickToBottomRef = React.useRef(true);

    const handleThreadScroll = () => {
        const el = scrollContainerRef.current;
        if (!el) return;
        stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    };

    React.useEffect(() => {
        const el = scrollContainerRef.current;
        if (el && stickToBottomRef.current) {
            el.scrollTop = el.scrollHeight;
        }
    }, [messages, agentStream.streamedResponse]);

    const updateMessage = React.useCallback(
        (id: string, patch: Partial<ChatItem>) => {
            setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
        },
        [setMessages]
    );

    const streamInto = async (query: string, assistantMsgId: string) => {
        if (!token) return;

        stickToBottomRef.current = true;
        setStreamingMsgId(assistantMsgId);
        setLiveStatus('Generating response…');

        try {
            const result = await agentStream.startStream({
                query,
                token,
                sessionId: activeSessionId || undefined
            });

            if (!result) {
                updateMessage(assistantMsgId, { content: streamedResponseRef.current, stopped: true });
                setLiveStatus('Response stopped.');
                return;
            }

            const currentSessionId = result.sessionId || activeSessionId;
            if (result.sessionId && !activeSessionId) {
                setActiveSessionId(result.sessionId);
            }

            if (currentSessionId && isGoogleUser) {
                setConversations((prev) => {
                    const now = new Date().toISOString();
                    const existing = prev.find((c) => c.id === currentSessionId);
                    const updatedItem: ChatConversation = existing
                        ? {
                              ...existing,
                              lastSnippet: query,
                              messageCount: (existing.messageCount || 0) + 2,
                              updatedAt: now
                          }
                        : {
                              id: currentSessionId,
                              userId: user?.id || '',
                              title: query.slice(0, 45) + (query.length > 45 ? '...' : ''),
                              createdAt: now,
                              updatedAt: now,
                              messageCount: 2,
                              lastSnippet: query
                          };
                    const nextList = [updatedItem, ...prev.filter((c) => c.id !== currentSessionId)];
                    persistConversations(nextList);
                    return nextList;
                });
                void loadConversations(true);
            }

            setMessages((prev) => {
                const next = prev.map((m) =>
                    m.id === assistantMsgId ? { ...m, content: result.response, citations: result.citations, error: undefined, stopped: false } : m
                );
                if (currentSessionId) {
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
            setLiveStatus('Response ready.');
        } catch (err: unknown) {
            const errorText = err instanceof Error ? err.message : 'Failed to execute agent stream.';
            if (err instanceof AgentStreamError && err.status === 429) {
                setQuotaRemaining(0);
            }
            updateMessage(assistantMsgId, { content: '', error: errorText });
            setLiveStatus(`Error: ${errorText}`);
        } finally {
            setStreamingMsgId(null);
        }
    };

    const sendQuery = (query: string) => {
        if (!query || agentStream.isStreaming) return;

        if (!token) {
            setDialogOpen(true);
            return;
        }

        if (quotaRemaining <= 0) {
            setHireMeModalOpen(true);
            return;
        }

        const userMsgId = `u-${Date.now()}`;
        const assistantMsgId = `a-${Date.now()}`;

        setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: query }, { id: assistantMsgId, role: 'assistant', content: '', query }]);
        setPrompt('');
        void streamInto(query, assistantMsgId);
    };

    const handleRetry = (msg: ChatItem) => {
        if (!msg.query || agentStream.isStreaming) return;
        if (quotaRemaining <= 0) {
            setHireMeModalOpen(true);
            return;
        }
        updateMessage(msg.id, { content: '', error: undefined, stopped: false });
        void streamInto(msg.query, msg.id);
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        sendQuery(prompt.trim());
    };

    const handleComposerKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            sendQuery(prompt.trim());
        }
    };

    const mobileTabs = [
        { id: 'workspace' as const, label: 'Workspace', icon: Database },
        { id: 'chat' as const, label: 'Canvas', icon: MessageSquare },
        { id: 'observability' as const, label: 'Observe', icon: Activity }
    ];

    return (
        <div className="h-screen flex flex-col bg-background text-foreground font-sans overflow-hidden">
            <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onLoad={() => setGisLoaded(true)} />

            {/* 1. Header */}
            <AppHeader
                user={user}
                quotaRemaining={quotaRemaining}
                bucketCapacity={bucketCapacity}
                isDarkTheme={isDarkTheme}
                onToggleTheme={handleToggleTheme}
                isObservabilityOpen={isObservabilityOpen}
                onToggleObservability={() => setIsObservabilityOpen((prev) => !prev)}
                isStreaming={agentStream.isStreaming}
                onOpenSignIn={() => setDialogOpen(true)}
                onLogout={logout}
            />

            {/* 4-Zone Body: Workspace (left) + Synthesis Canvas (center) + Observability (right) */}
            <div className="flex-1 flex overflow-hidden">
                {/* 2. Workspace Panel (Left) */}
                <WorkspaceSidebar
                    mobileActiveTab={mobileActiveTab}
                    openCategories={openCategories}
                    onToggleCategory={toggleCategory}
                    docs={docs}
                    docsError={docsError}
                    selectedCitationDoc={selectedCitationDoc}
                    token={token}
                    uploadState={uploadState}
                    fileInputRef={fileInputRef}
                    onUploadClick={handleUploadClick}
                    onFileSelected={handleFileSelected}
                    onInquireAuthor={() => setHireMeModalOpen(true)}
                    isGoogleUser={isGoogleUser}
                    activeSessionId={activeSessionId}
                    conversations={conversations}
                    isLoadingConversations={isLoadingConversations}
                    chatSearchQuery={chatSearchQuery}
                    onSearchChange={setChatSearchQuery}
                    onSelectConversation={handleSelectConversationItem}
                    onDeleteConversation={handleDeleteConversation}
                    onPrefetchConversation={prefetchMessages}
                    onOpenSignIn={() => setDialogOpen(true)}
                    chatNotice={chatNotice}
                    apiBase={API_BASE}
                />

                {/* 3. Active Chat Canvas (Center) */}
                <ChatCanvas
                    mobileActiveTab={mobileActiveTab}
                    user={user}
                    quotaRemaining={quotaRemaining}
                    messages={messages}
                    isStreaming={agentStream.isStreaming}
                    streamedResponse={agentStream.streamedResponse}
                    citations={agentStream.citations}
                    currentNode={agentStream.currentNode}
                    streamingMsgId={streamingMsgId}
                    isDarkTheme={isDarkTheme}
                    liveStatus={liveStatus}
                    scrollContainerRef={scrollContainerRef}
                    onScroll={handleThreadScroll}
                    onNewChat={handleNewChat}
                    onRetry={handleRetry}
                    onCitationClick={handleCitationClick}
                    onHireMeClick={() => setHireMeModalOpen(true)}
                    onSelectPrompt={(text) => setPrompt(text)}
                >
                    <Composer
                        prompt={prompt}
                        onPromptChange={setPrompt}
                        onSubmit={handleSubmit}
                        onKeyDown={handleComposerKeyDown}
                        isStreaming={agentStream.isStreaming}
                        onStop={agentStream.cancelStream}
                    />
                </ChatCanvas>

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
                    className={mobileActiveTab === 'observability' ? 'flex' : isObservabilityOpen ? 'hidden xl:flex' : 'hidden'}
                />
            </div>

            {/* Mobile Bottom Navigation */}
            <nav aria-label="Panels" className="xl:hidden flex items-center justify-around bg-card border-t border-border p-2 shrink-0 z-40 pb-safe">
                {mobileTabs.map(({ id, label, icon: Icon }) => {
                    const isActive = mobileActiveTab === id;
                    return (
                        <button
                            key={id}
                            type="button"
                            onClick={() => setMobileActiveTab(id)}
                            aria-current={isActive ? 'page' : undefined}
                            className={`flex flex-col items-center p-2 rounded-lg min-w-[70px] min-h-11 cursor-pointer ${
                                isActive ? 'text-primary bg-primary/10 font-bold' : 'text-muted-foreground hover:bg-secondary/50 font-medium'
                            }`}
                        >
                            <Icon className="h-5 w-5" aria-hidden="true" />
                            <span className="text-[11px] mt-1">{label}</span>
                        </button>
                    );
                })}
            </nav>

            {/* Modals */}
            <SignInDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                googleClientId={googleClientId}
                gisLoaded={gisLoaded}
                isGoogleLoading={isGoogleLoading}
                isGuestLoading={isGuestLoading}
                error={error}
                onGuestLogin={async () => {
                    const ok = await loginGuest();
                    if (ok) setDialogOpen(false);
                }}
                renderGoogleButton={renderGoogleButton}
            />
            <HireMeModal open={hireMeModalOpen} onOpenChange={setHireMeModalOpen} />
        </div>
    );
}
