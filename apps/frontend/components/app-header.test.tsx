import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vite-plus/test';
import type { UserSession } from '@nexusagent/contracts';
import { AppHeader } from './app-header';
import userEvent from '@testing-library/user-event';

const user: UserSession = { id: 'u1', name: 'Ada Lovelace', email: 'ada@example.com', isGuest: false, createdAt: '', lastSeenAt: '' };

function renderHeader(overrides: Partial<React.ComponentProps<typeof AppHeader>> = {}) {
    return render(
        <AppHeader
            user={user}
            quotaRemaining={3}
            bucketCapacity={25}
            isDarkTheme={false}
            onToggleTheme={() => {}}
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

    it('offers sign in when there is no session', () => {
        renderHeader({ user: null });
        expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument();
        expect(screen.queryByTestId('quota-badge')).not.toBeInTheDocument();
    });
});
