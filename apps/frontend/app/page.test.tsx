import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vite-plus/test';
import { useAuthStore } from '@/lib/auth-store';
import Home from './page';

describe('Home Page - Layout and Header Controls', () => {
    beforeEach(() => {
        localStorage.clear();
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
        expect(screen.getByRole('complementary', { name: /^workspace$/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 1')).not.toBeInTheDocument();

        // 3. Active Chat Canvas
        expect(screen.getByRole('main', { name: /active chat canvas/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 2')).not.toBeInTheDocument();

        // 4. Observability Panel
        expect(screen.getByRole('complementary', { name: /agent telemetry & observability/i })).toBeInTheDocument();
        expect(screen.queryByText('Zone 3')).not.toBeInTheDocument();
    });

    it('toggles agent observability panel from header button and collapse chevron', async () => {
        const user = userEvent.setup();
        render(<Home />);

        const obsPanel = screen.getByRole('complementary', { name: /agent telemetry & observability/i });
        // Initially default collapsed
        expect(obsPanel.className).toContain('hidden');
        expect(obsPanel.className).not.toContain('hidden xl:flex');

        // Click header toggle button to open
        const toggleBtn = screen.getByRole('button', { name: /toggle agent telemetry and observability panel/i });
        await user.click(toggleBtn);
        expect(obsPanel.className).toContain('hidden xl:flex');

        // Click panel header collapse button to close
        const collapseBtn = screen.getByRole('button', { name: /collapse observability panel/i });
        await user.click(collapseBtn);
        expect(obsPanel.className).toContain('hidden');
        expect(obsPanel.className).not.toContain('hidden xl:flex');
    });

    it('opens sign in dialog with google and guest sign in options when clicking sign in', async () => {
        const user = userEvent.setup();
        render(<Home />);

        const signInButton = screen.getByRole('button', { name: /^sign in$/i });
        await user.click(signInButton);

        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Sign In to NexusAgent' })).toBeInTheDocument();
        expect(screen.getByText(/sign-in isn.t configured/i)).toBeInTheDocument();
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

        render(<Home />);

        // Authenticate via store
        await act(async () => {
            await useAuthStore.getState().loginGoogle('google-id-token');
        });

        // Header shows avatar button for authenticated user
        const profileBtn = await screen.findByRole('button', { name: /user profile menu/i });
        expect(profileBtn).toBeInTheDocument();

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

    it('renders stream errors in the assistant bubble with a retry action instead of an endless spinner', async () => {
        const guest = {
            user: { id: '55555555-5555-5555-5555-555555555555', email: null, name: 'Guest Five', avatarUrl: null, isGuest: true },
            tokens: { accessToken: 'mock.jwt.token', tokenType: 'bearer', expiresIn: 86400 },
            quotaRemaining: 5,
            bucketCapacity: 5
        };
        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockImplementation(async (url: string) => {
            if (String(url).includes('/api/agent/stream')) {
                return { ok: false, status: 500, text: async () => '{"detail": "Synthesis backend unavailable"}' } as unknown as Response;
            }
            return { ok: true, json: async () => guest } as unknown as Response;
        });

        const user = userEvent.setup();
        render(<Home />);
        await user.click(screen.getByRole('button', { name: /^sign in$/i }));
        await user.click(screen.getByRole('button', { name: /start as guest/i }));
        await screen.findByRole('button', { name: /user profile menu/i });

        await user.type(screen.getByRole('textbox', { name: /architecture question/i }), 'Explain Raft quorum{Enter}');

        const errorBubble = await screen.findByTestId('assistant-error');
        expect(errorBubble).toHaveTextContent('Synthesis backend unavailable');
        expect(screen.queryByText(/synthesizing response/i)).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeEnabled();

        global.fetch = originalFetch;
    });

    it('shows the quota alert when the stream is rejected with 429', async () => {
        const guest = {
            user: { id: '66666666-6666-6666-6666-666666666666', email: null, name: 'Guest Six', avatarUrl: null, isGuest: true },
            tokens: { accessToken: 'mock.jwt.token', tokenType: 'bearer', expiresIn: 86400 },
            quotaRemaining: 5,
            bucketCapacity: 5
        };
        const originalFetch = global.fetch;
        global.fetch = vi.fn().mockImplementation(async (url: string) => {
            if (String(url).includes('/api/agent/stream')) {
                return { ok: false, status: 429, text: async () => '{"detail": "bucket empty"}' } as unknown as Response;
            }
            return { ok: true, json: async () => guest } as unknown as Response;
        });

        const user = userEvent.setup();
        render(<Home />);
        await user.click(screen.getByRole('button', { name: /^sign in$/i }));
        await user.click(screen.getByRole('button', { name: /start as guest/i }));
        await screen.findByRole('button', { name: /user profile menu/i });

        await user.type(screen.getByRole('textbox', { name: /architecture question/i }), 'Hello{Enter}');

        expect(await screen.findByTestId('assistant-error')).toHaveTextContent(/quota exhausted/i);
        expect(screen.getByText(/used all your free questions/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /send query/i })).toBeDisabled();
        // The live region announces the failure to screen-reader users as well
        expect(screen.getByRole('status', { name: '' })).toHaveTextContent(/quota exhausted/i);

        global.fetch = originalFetch;
    });

    it('clears cached chat history from localStorage on sign out', () => {
        localStorage.setItem('nexusagent_chat_history_user-1', '[]');
        localStorage.setItem('nexusagent_msgs_conv-1', '[]');
        localStorage.setItem('nexusagent_theme', 'dark');

        useAuthStore.getState().logout();

        expect(localStorage.getItem('nexusagent_chat_history_user-1')).toBeNull();
        expect(localStorage.getItem('nexusagent_msgs_conv-1')).toBeNull();
        expect(localStorage.getItem('nexusagent_theme')).toBe('dark');
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
        localStorage.setItem('nexusagent_quota', JSON.stringify({ remaining: 25, capacity: 25, resetsAt: null }));

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
