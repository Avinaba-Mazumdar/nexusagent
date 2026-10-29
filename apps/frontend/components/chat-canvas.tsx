'use client';

import * as React from 'react';
import { AlertCircle, Bot, Briefcase, Info, Loader2, Plus, RotateCcw, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { MarkdownRenderer } from '@/components/canvas';
import { STARTER_PROMPTS } from '@/lib/starter-prompts';
import type { UserSession, Citation } from '@nexusagent/contracts';
import type { ChatItem } from '@/hooks/useChatHistory';

export interface ChatCanvasProps {
    mobileActiveTab: 'workspace' | 'chat' | 'observability';
    user: UserSession | null;
    quotaRemaining: number;
    quotaResetsAt: string | null;
    messages: ChatItem[];
    isStreaming: boolean;
    streamedResponse: string;
    citations: Citation[];
    currentNode: string | null;
    streamingMsgId: string | null;
    isDarkTheme: boolean;
    liveStatus: string;
    scrollContainerRef: React.RefObject<HTMLDivElement | null>;
    onScroll: () => void;
    onNewChat: () => void;
    onRetry: (msg: ChatItem) => void;
    onCitationClick: (cite: Citation) => void;
    onHireMeClick: () => void;
    onSelectPrompt: (promptText: string) => void;
    children: React.ReactNode;
}

const NODE_STATUS: Record<string, string> = {
    planner: 'Planning…',
    retriever: 'Searching sources…',
    grounding: 'Checking sources…',
    synthesizer: 'Writing answer…'
};

function formatResetTime(iso: string | null): string {
    if (!iso) return 'within the hour';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'within the hour';
    return `at ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
}

export function ChatCanvas({
    mobileActiveTab,
    user,
    quotaRemaining,
    quotaResetsAt,
    messages,
    isStreaming,
    streamedResponse,
    citations,
    currentNode,
    streamingMsgId,
    isDarkTheme,
    liveStatus,
    scrollContainerRef,
    onScroll,
    onNewChat,
    onRetry,
    onCitationClick,
    onHireMeClick,
    onSelectPrompt,
    children
}: ChatCanvasProps) {
    return (
        <main
            id="main-canvas"
            role="main"
            aria-label="Active Chat Canvas"
            className={`relative flex-1 flex-col overflow-hidden bg-background ${mobileActiveTab === 'chat' ? 'flex' : 'hidden xl:flex'}`}
        >
            {/* Toolbar: sits above the thread so it never covers messages or tables */}
            <div className="flex items-center justify-between gap-2 px-4 md:px-6 py-2 border-b border-border/60 bg-background shrink-0">
                <span className="text-xs text-muted-foreground truncate">
                    {user?.isGuest ? "Guest chats aren't saved and don't remember earlier questions. Sign in with Google to keep context." : ''}
                </span>
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onNewChat}
                    disabled={isStreaming}
                    title="Start New Chat"
                    aria-label="New Chat"
                    className="h-9 px-3 rounded-xl border border-border/80 bg-card hover:bg-secondary text-foreground shadow-xs flex items-center gap-1.5 font-medium text-xs shrink-0"
                >
                    <Plus className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                    <span>New Chat</span>
                </Button>
            </div>

            <div ref={scrollContainerRef} onScroll={onScroll} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
                {/* Quota exhausted: say when it comes back */}
                {user && quotaRemaining <= 0 && (
                    <div
                        role="alert"
                        className="p-4 rounded-xl border border-warning-border bg-warning-bg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-sm"
                    >
                        <div>
                            <p className="font-bold text-foreground">You&apos;ve used all your free questions</p>
                            <p className="text-muted-foreground text-xs mt-0.5">Your quota refills {formatResetTime(quotaResetsAt)}.</p>
                        </div>
                        <Button size="sm" variant="outline" onClick={onHireMeClick} className="text-xs font-semibold rounded-xl h-8 gap-1 shrink-0">
                            <Briefcase className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>Need more?</span>
                        </Button>
                    </div>
                )}

                {/* Messages Thread */}
                {messages.length === 0 ? (
                    <Card className="shadow-xs border-border">
                        <CardHeader className="p-4 pb-2">
                            <CardTitle className="text-base font-heading font-bold text-foreground flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
                                Autonomous Systems Intelligence
                            </CardTitle>
                            <CardDescription className="text-sm text-muted-foreground">
                                Answers grounded in AI model benchmarks (BenchLM, OpenRouter, CursorBench, Artificial Analysis) and your uploaded documents.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="p-4 pt-2 space-y-3">
                            <div className="p-3.5 rounded-xl bg-secondary/40 border border-border text-sm text-muted-foreground leading-relaxed">
                                Ask about benchmark comparisons, pricing, or distributed-systems trade-offs.
                            </div>
                            <div className="flex flex-wrap gap-2 pt-1">
                                {STARTER_PROMPTS.map((promptText) => (
                                    <button
                                        key={promptText}
                                        type="button"
                                        onClick={() => onSelectPrompt(promptText)}
                                        className="text-xs px-3 py-2 rounded-lg border border-border/80 bg-card hover:bg-secondary text-foreground text-left transition-colors cursor-pointer"
                                    >
                                        &ldquo;{promptText}&rdquo;
                                    </button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-4">
                        {messages.map((msg) => {
                            const isStreamingThis = isStreaming && msg.id === streamingMsgId;
                            return (
                                <div key={msg.id} className={`flex gap-3 text-sm leading-relaxed ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    {msg.role === 'assistant' && (
                                        <div className="h-7 w-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 mt-0.5">
                                            <Bot className="h-4 w-4" aria-hidden="true" />
                                        </div>
                                    )}
                                    <div
                                        className={`p-3.5 rounded-2xl min-w-0 ${
                                            msg.role === 'user'
                                                ? 'max-w-2xl bg-primary text-primary-foreground font-medium rounded-tr-xs whitespace-pre-wrap break-words'
                                                : 'max-w-3xl xl:max-w-4xl bg-card border border-border text-foreground shadow-2xs rounded-tl-xs w-full'
                                        }`}
                                    >
                                        {msg.role === 'user' ? (
                                            msg.content
                                        ) : isStreamingThis ? (
                                            streamedResponse ? (
                                                <MarkdownRenderer
                                                    content={streamedResponse}
                                                    isStreaming={true}
                                                    citations={citations}
                                                    isDark={isDarkTheme}
                                                    onCitationClick={onCitationClick}
                                                />
                                            ) : (
                                                <div className="flex items-center gap-1.5 text-muted-foreground">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                                                    <span>{NODE_STATUS[currentNode ?? 'planner'] ?? 'Working…'}</span>
                                                </div>
                                            )
                                        ) : msg.error ? (
                                            <div className="space-y-2" data-testid="assistant-error">
                                                <p className="flex items-start gap-1.5 text-destructive font-medium">
                                                    <AlertCircle className="h-4 w-4 shrink-0 mt-px" aria-hidden="true" />
                                                    <span>{msg.error}</span>
                                                </p>
                                                {msg.query && (
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => onRetry(msg)}
                                                        disabled={isStreaming}
                                                        className="h-8 text-xs rounded-lg gap-1.5"
                                                    >
                                                        <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                                                        Retry
                                                    </Button>
                                                )}
                                            </div>
                                        ) : (
                                            <>
                                                {msg.content ? (
                                                    <MarkdownRenderer content={msg.content} citations={msg.citations} isDark={isDarkTheme} onCitationClick={onCitationClick} />
                                                ) : (
                                                    !msg.stopped && <span className="text-muted-foreground italic">No response.</span>
                                                )}
                                                {msg.warnings && msg.warnings.length > 0 && (
                                                    <p className="mt-2 flex items-start gap-1.5 text-xs text-muted-foreground" data-testid="injection-warning">
                                                        <Info className="h-3.5 w-3.5 shrink-0 mt-px" aria-hidden="true" />
                                                        <span>
                                                            {msg.warnings.map((w) => w.filename).join(', ')} contains instruction-like text. It was treated as data, not as
                                                            instructions.
                                                        </span>
                                                    </p>
                                                )}
                                                {msg.stopped && (
                                                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                                                        <span>Generation stopped.</span>
                                                        {msg.query && (
                                                            <button
                                                                type="button"
                                                                onClick={() => onRetry(msg)}
                                                                disabled={isStreaming}
                                                                className="text-primary hover:underline cursor-pointer disabled:opacity-50"
                                                            >
                                                                Regenerate
                                                            </button>
                                                        )}
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Screen-reader announcements for run status */}
            <div className="sr-only" role="status" aria-live="polite">
                {liveStatus}
            </div>

            {children}
        </main>
    );
}
