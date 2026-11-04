import * as React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vite-plus/test';
import { ObservabilityPanel } from './observability-panel';

describe('ObservabilityPanel Component', () => {
    it('renders token tiles with calculated numbers', () => {
        render(
            <ObservabilityPanel
                logs={[]}
                usage={[
                    {
                        sessionId: 's1',
                        step: 'router',
                        model: 'gemini-2.5-flash',
                        inputTokens: 50,
                        outputTokens: 10,
                        totalTokens: 60
                    },
                    {
                        sessionId: 's1',
                        step: 'answer',
                        model: 'gemini-2.5-pro',
                        inputTokens: 200,
                        outputTokens: 40,
                        totalTokens: 240
                    }
                ]}
                sessionTokens={{ input: 350, output: 70, total: 420 }}
            />
        );

        // Input tokens: 50 + 200 = 250
        expect(screen.getByText('250')).toBeInTheDocument();
        // Output tokens: 10 + 40 = 50
        expect(screen.getByText('50')).toBeInTheDocument();
        // Total tokens: 60 + 240 = 300
        expect(screen.getByText('300')).toBeInTheDocument();
        // Session total: 420
        expect(screen.getByText('420')).toBeInTheDocument();
        // Models listed
        expect(screen.getByText(/gemini-2.5-flash, gemini-2.5-pro/)).toBeInTheDocument();
    });

    it('renders tool calls with tool name, query summary, results count and duration', () => {
        render(
            <ObservabilityPanel
                logs={[]}
                toolCalls={[
                    {
                        tool: 'google_search',
                        args: { queries: ['weather Bengaluru'] },
                        durationMs: 120,
                        resultsCount: 2
                    },
                    {
                        tool: 'hybrid_rag_search',
                        args: { query: 'CursorBench comparison', limit: 5 },
                        durationMs: 45,
                        resultsCount: 5
                    }
                ]}
            />
        );

        expect(screen.getByText('google_search')).toBeInTheDocument();
        expect(screen.getByText('weather Bengaluru')).toBeInTheDocument();
        expect(screen.getByText('120ms')).toBeInTheDocument();

        expect(screen.getByText('hybrid_rag_search')).toBeInTheDocument();
        expect(screen.getByText('CursorBench comparison')).toBeInTheDocument();
        expect(screen.getByText('45ms')).toBeInTheDocument();
    });

    it('renders pipeline stages based on node history', () => {
        render(<ObservabilityPanel logs={[]} nodeHistory={['router', 'chat']} currentNode="chat" />);

        expect(screen.getByText('Router')).toBeInTheDocument();
        expect(screen.getByText('Chat')).toBeInTheDocument();
    });
});
