'use client';

import * as React from 'react';
import { Send, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface ComposerProps {
    prompt: string;
    onPromptChange: (value: string) => void;
    onSubmit: (e: React.FormEvent) => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    isStreaming: boolean;
    onStop: () => void;
}

export function Composer({
    prompt,
    onPromptChange,
    onSubmit,
    onKeyDown,
    isStreaming,
    onStop
}: ComposerProps) {
    return (
        <form onSubmit={onSubmit} aria-label="Ask NexusAgent" className="p-4 bg-card border-t border-border shrink-0">
            <div className="relative flex items-end">
                <textarea
                    value={prompt}
                    onChange={(e) => onPromptChange(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    aria-label="Architecture question"
                    placeholder="Ask an architecture question or query the benchmark knowledge base..."
                    className="w-full resize-none [field-sizing:content] min-h-11 max-h-40 py-3 pl-3 pr-24 text-xs leading-relaxed rounded-xl bg-secondary/40 border border-border text-foreground placeholder:text-muted-foreground focus-visible:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                        disabled={!prompt.trim()}
                        aria-label="Send query"
                        className="absolute right-1.5 bottom-1.5 h-8 px-4 text-xs rounded-lg gap-1.5 font-bold"
                    >
                        <span>Send</span>
                        <Send className="h-3 w-3" aria-hidden="true" />
                    </Button>
                )}
            </div>
            <p className="hidden sm:block mt-1.5 text-[10px] text-muted-foreground">Enter to send • Shift+Enter for a new line</p>
        </form>
    );
}

