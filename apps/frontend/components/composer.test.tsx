import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vite-plus/test';
import { Composer } from './composer';
import { MAX_QUERY_CHARS } from '@/lib/limits';

function renderComposer(prompt: string, overrides: Partial<React.ComponentProps<typeof Composer>> = {}) {
    return render(
        <Composer
            prompt={prompt}
            onPromptChange={() => {}}
            onSubmit={(e) => e.preventDefault()}
            onKeyDown={() => {}}
            isStreaming={false}
            onStop={() => {}}
            {...overrides}
        />
    );
}

describe('Composer', () => {
    it('limits the textarea to the server maximum', () => {
        renderComposer('');
        expect(screen.getByLabelText('Architecture question')).toHaveAttribute('maxlength', String(MAX_QUERY_CHARS));
    });

    it('shows the counter only close to the limit', () => {
        const { rerender } = renderComposer('a'.repeat(1600));
        expect(screen.queryByText(/\/2000/)).not.toBeInTheDocument();

        rerender(
            <Composer prompt={'a'.repeat(1601)} onPromptChange={() => {}} onSubmit={() => {}} onKeyDown={() => {}} isStreaming={false} onStop={() => {}} />
        );
        expect(screen.getByText('1601/2000')).toBeInTheDocument();
        expect(screen.getByLabelText('Architecture question')).toHaveAttribute('aria-describedby', 'query-counter');
    });

    it('disables Send for an empty prompt and sends on submit', async () => {
        const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
        renderComposer('hello', { onSubmit });
        await userEvent.click(screen.getByRole('button', { name: /send query/i }));
        expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    it('disables Send when the quota is exhausted', () => {
        renderComposer('hello', { quotaExhausted: true });
        expect(screen.getByRole('button', { name: /send query/i })).toBeDisabled();
    });
});
