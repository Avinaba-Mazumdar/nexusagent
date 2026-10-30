'use client';

import * as React from 'react';
import { Send, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MAX_QUERY_CHARS, QUERY_COUNTER_FROM } from '@/lib/limits';

const MAX_HEIGHT_PX = 160;

export interface ComposerProps {
    prompt: string;
    onPromptChange: (value: string) => void;
    onSubmit: (e: React.FormEvent) => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    isStreaming: boolean;
    onStop: () => void;
    /** Signed in but out of free questions: sending is disabled until the quota refills. */
    quotaExhausted?: boolean;
}

export function Composer({ prompt, onPromptChange, onSubmit, onKeyDown, isStreaming, onStop, quotaExhausted = false }: ComposerProps) {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    // Auto-grow without relying on CSS `field-sizing` (missing in Firefox and older Safari).
    React.useLayoutEffect(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
    }, [prompt]);

    const showCounter = prompt.length > QUERY_COUNTER_FROM;

    return (
        <form onSubmit={onSubmit} aria-label="Ask NexusAgent" className="p-4 bg-card border-t border-border shrink-0">
            <div className="relative flex items-end">
                <textarea
                    ref={textareaRef}
                    value={prompt}
                    onChange={(e) => onPromptChange(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    aria-label="Architecture question"
                    maxLength={MAX_QUERY_CHARS}
                    aria-describedby={showCounter ? 'query-counter' : undefined}
                    placeholder={quotaExhausted ? 'Out of free questions for now' : 'Ask an architecture question or query the benchmark knowledge base...'}
                    className="w-full resize-none min-h-11 max-h-40 py-3 pl-3 pr-24 text-sm leading-relaxed rounded-xl bg-secondary/40 border border-border text-foreground placeholder:text-muted-foreground focus-visible:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                {isStreaming ? (
                    <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={onStop}
                        aria-label="Stop generating"
                        className="absolute right-1.5 bottom-1.5 h-8 px-3 text-xs rounded-lg gap-1.5 font-bold"
                    >
                        <Square className="h-3 w-3 fill-current" aria-hidden="true" />
                        <span>Stop</span>
                    </Button>
                ) : (
                    <Button
                        type="submit"
                        size="sm"
                        variant="default"
                        disabled={!prompt.trim() || quotaExhausted}
                        aria-label="Send query"
                        className="absolute right-1.5 bottom-1.5 h-8 px-4 text-xs rounded-lg gap-1.5 font-bold"
                    >
                        <span>Send</span>
                        <Send className="h-3 w-3" aria-hidden="true" />
                    </Button>
                )}
            </div>
            {showCounter && (
                <p id="query-counter" className={`mt-1.5 text-xs ${prompt.length >= MAX_QUERY_CHARS ? 'text-destructive' : 'text-muted-foreground'}`}>
                    {prompt.length}/{MAX_QUERY_CHARS}
                </p>
            )}
            <p className="hidden sm:block mt-1.5 text-xs text-muted-foreground">Enter to send • Shift+Enter for a new line</p>
        </form>
    );
}
