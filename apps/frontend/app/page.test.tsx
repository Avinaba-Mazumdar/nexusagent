import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useAuthStore } from '@/lib/auth-store';
import Home from './page';

describe('Home Page - Layout and Header Controls', () => {
    beforeEach(() => {
        localStorage.clear();
        document.cookie = 'nexusagent_token=; path=/; max-age=0';
        useAuthStore.getState().logout();
    });

    it('renders the 4 primary layout elements without versions, quotas, or zone tags', () => {
        render(<Home />);

        // 1. Header
        expect(screen.getByRole('banner', { name: /command center navigation/i })).toBeInTheDocument();
        expect(screen.getByText('NexusAgent')).toBeInTheDocument();
        expect(screen.queryByText('v0.1.0')).not.toBeInTheDocument();
        expect(screen.queryByText(/quota/i)).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument();

        // 2. Workspace Panel
        expect(screen.getByRole('complementary', { name: /workspace & tools/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 1')).not.toBeInTheDocument();

        // 3. Active Chat Canvas
        expect(screen.getByRole('main', { name: /active chat canvas/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 2')).not.toBeInTheDocument();

        // 4. Observability Panel
        expect(screen.getByRole('complementary', { name: /agent telemetry & observability/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 3')).not.toBeInTheDocument();
    });

    it('opens sign in dialog with google and guest sign in options when clicking sign in', async () => {
        const user = userEvent.setup();
        render(<Home />);

        const signInButton = screen.getByRole('button', { name: /^sign in$/i });
        await user.click(signInButton);

        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Sign In to NexusAgent' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /continue with google/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /start as guest/i })).toBeInTheDocument();
        expect(screen.queryByRole('tab', { name: /email account/i })).not.toBeInTheDocument();
    });

    it('authenticates guest, displays session header with quota, and signs out', async () => {
        const mockGuestResponse = {
            user: {
                id: '11111111-1111-1111-1111-111111111111',
                email: null,
                name: 'Guest Architect #111111',
                avatarUrl: null,
                isGuest: true,
                createdAt: '2026-09-13T00:00:00Z',
                lastSeenAt: '2026-09-13T00:00:00Z'
            },
            tokens: {
                accessToken: 'mock.jwt.token',
                tokenType: 'bearer',
                expiresIn: 86400
            },
            quotaRemaining: 5,
            bucketCapacity: 5
        };

        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => mockGuestResponse
        } as unknown as Response);

        const user = userEvent.setup();
        render(<Home />);

        // Open Dialog
        const signInButton = screen.getByRole('button', { name: /^sign in$/i });
        await user.click(signInButton);

        // Click Guest Sign In
        const guestButton = screen.getByRole('button', { name: /start as guest/i });
        await user.click(guestButton);

        // Header shows avatar button
        const profileBtn = await screen.findByRole('button', { name: /user profile menu/i });
        expect(profileBtn).toBeInTheDocument();

        // Click Avatar to open Popover
        await user.click(profileBtn);

        // Popover shows user name and quota
        expect(await screen.findByText('Guest Architect #111111')).toBeInTheDocument();
        expect(screen.getByText('5/5 Quota')).toBeInTheDocument();

        // Left sidebar Chats category prompts guest user to sign in
        expect(screen.getByText('Sign in to save chat history')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /toggle chat history/i })).not.toBeInTheDocument();

        // Sign out restores Sign In button
        const signOutButton = screen.getByRole('button', { name: /sign out/i });
        await user.click(signOutButton);

        expect(await screen.findByRole('button', { name: /^sign in$/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /user profile menu/i })).not.toBeInTheDocument();

        global.fetch = originalFetch;
    });

    it('authenticates with Google sign in', async () => {
        const mockAuthResponse = {
            accessToken: 'google.jwt.token',
            tokenType: 'bearer',
            expiresIn: 86400,
            user: {
                id: '44444444-4444-4444-4444-444444444444',
                email: 'developer@nexusagent.internal',
                name: 'Lead Systems Architect',
                avatarUrl: null,
                isGuest: false,
                createdAt: '2026-09-13T00:00:00Z',
                lastSeenAt: '2026-09-13T00:00:00Z'
            }
        };

        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => mockAuthResponse
        } as unknown as Response);

        const user = userEvent.setup();
        render(<Home />);

        // Open Dialog
        await user.click(screen.getByRole('button', { name: /^sign in$/i }));

        // Click Google Sign In
        await user.click(screen.getByRole('button', { name: /continue with google/i }));

        // Header shows avatar button for authenticated user
        const profileBtn = await screen.findByRole('button', { name: /user profile menu/i });
        expect(profileBtn).toBeInTheDocument();

        // Verify cookie persistence
        expect(document.cookie).toContain('nexusagent_token=google.jwt.token');

        // Collapsible Chats category displays search input and new chat button in sidebar
        expect(await screen.findByRole('searchbox', { name: /search conversation history/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /new chat/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /toggle chat history/i })).not.toBeInTheDocument();

        global.fetch = originalFetch;
    });

    it('toggles dark theme and persists choice in localStorage', async () => {
        const mockGuestResponse = {
            user: {
                id: '22222222-2222-2222-2222-222222222222',
                email: null,
                name: 'Guest Tester',
                avatarUrl: null,
                isGuest: true,
                createdAt: '2026-09-13T00:00:00Z',
                lastSeenAt: '2026-09-13T00:00:00Z'
            },
            tokens: {
                accessToken: 'mock.jwt.token',
                tokenType: 'bearer',
                expiresIn: 86400
            },
            quotaRemaining: 5,
            bucketCapacity: 5
        };

        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => mockGuestResponse
        } as unknown as Response);

        const user = userEvent.setup();
        render(<Home />);

        // Login guest
        await user.click(screen.getByRole('button', { name: /^sign in$/i }));
        await user.click(screen.getByRole('button', { name: /start as guest/i }));

        // Open profile popover
        const profileBtn = await screen.findByRole('button', { name: /user profile menu/i });
        await user.click(profileBtn);

        // Find theme switch
        const themeSwitch = screen.getByRole('switch', { name: /toggle dark mode theme/i });
        expect(themeSwitch).toBeInTheDocument();

        // Toggle on -> dark class added & stored
        await user.click(themeSwitch);
        expect(document.documentElement.classList.contains('dark')).toBe(true);
        expect(localStorage.getItem('nexusagent_theme')).toBe('dark');

        // Toggle off -> dark class removed & light stored
        await user.click(themeSwitch);
        expect(document.documentElement.classList.contains('dark')).toBe(false);
        expect(localStorage.getItem('nexusagent_theme')).toBe('light');

        global.fetch = originalFetch;
    });

    it('invalidates stale session when server returns 401 on init', async () => {
        localStorage.setItem('nexusagent_token', 'stale.jwt.token');
        localStorage.setItem(
            'nexusagent_user',
            JSON.stringify({
                id: '33333333-3333-3333-3333-333333333333',
                email: 'deleted@nexusagent.internal',
                name: 'Deleted User',
                avatarUrl: null,
                isGuest: false,
                createdAt: '2026-09-13T00:00:00Z',
                lastSeenAt: '2026-09-13T00:00:00Z'
            })
        );
        localStorage.setItem('nexusagent_quota', '25');

        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            json: async () => ({ detail: 'User not found' })
        } as unknown as Response);

        render(<Home />);

        // Should revert to logged-out state with Sign In button visible
        expect(await screen.findByRole('button', { name: /^sign in$/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /user profile menu/i })).not.toBeInTheDocument();
        expect(localStorage.getItem('nexusagent_token')).toBeNull();

        global.fetch = originalFetch;
    });
});
