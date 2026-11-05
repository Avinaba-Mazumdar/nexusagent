import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vite-plus/test';
import type { UserSession } from '@nexusagent/contracts';
import { AppHeader } from './app-header';
import userEvent from '@testing-library/user-event';

const user: UserSession = { id: 'u1', name: 'Ada Lovelace', email: 'ada@example.com', isGuest: false, isAdmin: false, createdAt: '', lastSeenAt: '' };

function renderHeader(overrides: Partial<React.ComponentProps<typeof AppHeader>> = {}) {
    return render(
        <AppHeader
            user={user}
            quotaRemaining={3}
            bucketCapacity={25}
            theme="light"
            onThemeChange={() => {}}
            isObservabilityOpen={false}
            onToggleObservability={() => {}}
            isStreaming={false}
            onOpenSignIn={() => {}}
            onLogout={() => {}}
            {...overrides}
        />
    );
}

describe('AppHeader', () => {
    it('shows the quota pill (visible on mobile too)', () => {
        renderHeader();
        const badge = screen.getByTestId('quota-badge');
        expect(badge).toHaveTextContent('3/25');
        expect(badge.className).not.toContain('hidden');
    });

    it('never renders NaN% in the quota bar while capacity is unknown (R2-UX-03)', async () => {
        renderHeader({ quotaRemaining: 0, bucketCapacity: 0 });
        await userEvent.click(screen.getByRole('button', { name: /user profile menu/i }));
        const bar = document.querySelector('.bg-primary.h-full') as HTMLElement;
        expect(bar.style.width).toBe('0%');
    });

    it('cycles Light -> Dark -> Black from the header button, signed out too', async () => {
        const onThemeChange = vi.fn();
        const { unmount } = renderHeader({ user: null, onThemeChange });
        await userEvent.click(screen.getByRole('button', { name: /switch to dark theme/i }));
        expect(onThemeChange).toHaveBeenLastCalledWith('dark');
        unmount();

        renderHeader({ user: null, theme: 'black', onThemeChange });
        await userEvent.click(screen.getByRole('button', { name: /switch to light theme/i }));
        expect(onThemeChange).toHaveBeenLastCalledWith('light');
    });

    it('offers Light, Dark and Black in the account menu radio group', async () => {
        const onThemeChange = vi.fn();
        renderHeader({ theme: 'dark', onThemeChange });
        await userEvent.click(screen.getByRole('button', { name: /user profile menu/i }));

        expect(screen.getByRole('radiogroup', { name: /colour theme/i })).toBeInTheDocument();
        expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['Light', 'Dark', 'Black']);
        expect(screen.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'true');

        await userEvent.click(screen.getByRole('radio', { name: 'Black' }));
        expect(onThemeChange).toHaveBeenLastCalledWith('black');

        screen.getByRole('radio', { name: 'Dark' }).focus();
        await userEvent.keyboard('{ArrowLeft}');
        expect(onThemeChange).toHaveBeenLastCalledWith('light');
    });

    it('offers sign in when there is no session', () => {
        renderHeader({ user: null });
        expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument();
        expect(screen.queryByTestId('quota-badge')).not.toBeInTheDocument();
    });
});
