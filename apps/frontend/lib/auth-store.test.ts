import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import { useAuthStore } from './auth-store';

function jwtExpiringIn(seconds: number): string {
    const encode = (value: object) => btoa(JSON.stringify(value)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
    return `${encode({ alg: 'HS256' })}.${encode({ exp: Math.floor(Date.now() / 1000) + seconds })}.signature`;
}

const user = { id: 'u1', name: 'Ada', email: 'ada@example.com', isGuest: false, createdAt: '', lastSeenAt: '' };

function mockApi(refreshedToken: string) {
    const calls: string[] = [];
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
        calls.push(url);
        const body = url.includes('/api/auth/me')
            ? { user, quota: { tokensRemaining: 7, bucketCapacity: 25, resetsAt: '2026-01-01T00:00:00Z' } }
            : { accessToken: refreshedToken, tokenType: 'bearer', expiresIn: 86400, user, quotaRemaining: 7, bucketCapacity: 25 };
        return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }) as typeof fetch;
    return calls;
}

describe('auth store session refresh (R2-LOG-11)', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null, token: null });
    });
    afterEach(() => {
        useAuthStore.getState().logout();
        vi.restoreAllMocks();
    });

    it('refreshes a token with two hours left exactly once on init', async () => {
        const old = jwtExpiringIn(2 * 60 * 60);
        const fresh = jwtExpiringIn(24 * 60 * 60);
        localStorage.setItem('nexusagent_token', old);
        localStorage.setItem('nexusagent_user', JSON.stringify(user));
        const calls = mockApi(fresh);

        await useAuthStore.getState().initAuth();

        expect(calls.filter((url) => url.includes('/api/auth/refresh'))).toHaveLength(1);
        expect(useAuthStore.getState().token).toBe(fresh);
        expect(localStorage.getItem('nexusagent_token')).toBe(fresh);
    });

    it('leaves a token with plenty of time left alone', async () => {
        const current = jwtExpiringIn(20 * 60 * 60);
        localStorage.setItem('nexusagent_token', current);
        localStorage.setItem('nexusagent_user', JSON.stringify(user));
        const calls = mockApi(jwtExpiringIn(24 * 60 * 60));

        await useAuthStore.getState().initAuth();

        expect(calls.some((url) => url.includes('/api/auth/refresh'))).toBe(false);
        expect(useAuthStore.getState().token).toBe(current);
    });

    it('clearing the session wipes cached chats (logout on a shared device)', () => {
        localStorage.setItem('nexusagent_token', 't');
        localStorage.setItem('nexusagent_msgs_abc', '[]');
        localStorage.setItem('nexusagent_chat_history_u1', '[]');
        useAuthStore.setState({ token: 't', user });
        mockApi('x');

        useAuthStore.getState().logout();

        expect(localStorage.getItem('nexusagent_msgs_abc')).toBeNull();
        expect(localStorage.getItem('nexusagent_chat_history_u1')).toBeNull();
        expect(useAuthStore.getState().token).toBeNull();
    });
});

describe('session notice (R2-UX-02)', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null, token: null, sessionNotice: null });
    });

    it('explains an expired session after a 401 and clears on the next sign-in', async () => {
        useAuthStore.setState({ token: 'stale', user });
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            statusText: 'Unauthorized',
            json: async () => ({ detail: 'Token has expired' })
        } as unknown as Response);
        const { apiClient } = await import('./api-client');

        await expect(apiClient('/api/auth/me')).rejects.toThrow();

        expect(useAuthStore.getState().token).toBeNull();
        expect(useAuthStore.getState().sessionNotice).toMatch(/session expired/i);

        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ tokens: { accessToken: 'new' }, user, quotaRemaining: 5, bucketCapacity: 5 })
        } as unknown as Response);
        await useAuthStore.getState().loginGuest();
        expect(useAuthStore.getState().sessionNotice).toBeNull();
        useAuthStore.getState().logout();
    });

    it('does not show the notice on a manual logout', () => {
        global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) } as unknown as Response);
        useAuthStore.setState({ token: 't', user });

        useAuthStore.getState().logout();

        expect(useAuthStore.getState().sessionNotice).toBeNull();
    });
});
