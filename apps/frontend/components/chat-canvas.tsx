'use client';

import * as React from 'react';
import {
    AlertCircle,
    Bot,
    Briefcase,
    Loader2,
    Plus,
    RotateCcw,
    Sparkles
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { MarkdownRenderer } from '@/components/canvas';
import type { UserSession, Citation } from '@nexusagent/contracts';
import type { ChatItem } from '@/hooks/useChatHistory';

export interface ChatCanvasProps {
    mobileActiveTab: 'workspace' | 'chat' | 'observability';
    user: UserSession | null;
    quotaRemaining: number;
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
    onCitationClick: (cite: { filename: string }) => void;
    onHireMeClick: () => void;
    onSelectPrompt: (promptText: string) => void;
    children: React.ReactNode;
}

export function ChatCanvas({
    mobileActiveTab,
    user,
    quotaRemaining,
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
            role="main"
            aria-label="Active Chat Canvas"
            className={`relative flex-1 flex-col overflow-hidden bg-background ${mobileActiveTab === 'chat' ? 'flex' : 'hidden xl:flex'}`}
        >
            {/* Floating New Chat Action Button */}
            <div className="absolute top-4 right-4 z-20">
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onNewChat}
                    disabled={isStreaming}
                    title="Start New Chat"
                    aria-label="New Chat"
                    className="h-9 px-3 rounded-xl border border-border/80 bg-card/90 hover:bg-secondary text-foreground shadow-sm backdrop-blur-xs flex items-center gap-1.5 font-medium text-xs cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                    <Plus className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                    <span>New Chat</span>
                </Button>
            </div>

            <div ref={scrollContainerRef as any} onScroll={onScroll} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
                {/* Quota Depleted Lead Magnet Alert */}
                {user && quotaRemaining <= 0 && (
                    <div
                        role="alert"
                        className="p-4 rounded-xl border border-warning-border bg-warning-bg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                    >
                        <div>
                            <p className="font-bold text-foreground">Demo Query Limit Reached</p>
                            <p className="text-muted-foreground text-[11px] mt-0.5">
                                Your free queries refill hourly. Need more, or a private deployment? Book a custom architecture build.
                            </p>
                        </div>
                        <Button
                            size="sm"
                            variant="default"
                            onClick={onHireMeClick}
                            className="text-xs font-bold rounded-xl h-8 gap-1 shrink-0"
                        >
                            <Briefcase className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>Hire Me</span>
                        </Button>
                    </div>
                )}

                {/* Messages Thread */}
                {messages.length === 0 ? (
                    <Card className="shadow-xs border-border">
                        <CardHeader className="p-4 pb-2">
                            <CardTitle className="text-sm font-heading font-bold text-foreground flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
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
                                        onClick={() => onSelectPrompt(promptText)}
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
                        {messages.map((msg) => {
                            const isStreamingThis = isStreaming && msg.id === streamingMsgId;
                            return (
                                <div
                                    key={msg.id}
                                    className={`flex gap-3 text-xs leading-relaxed ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
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
                                                    <span>Executing DAG [{currentNode?.toUpperCase() || 'PLANNER'}]...</span>
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
                                                    <MarkdownRenderer
                                                        content={msg.content}
                                                        citations={msg.citations}
                                                        isDark={isDarkTheme}
                                                        onCitationClick={onCitationClick}
                                                    />
                                                ) : (
                                                    !msg.stopped && <span className="text-muted-foreground italic">No response.</span>
                                                )}
                                                {msg.stopped && (
                                                    <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
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

