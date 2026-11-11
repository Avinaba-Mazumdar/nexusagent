import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test';
import { useAuthStore } from './auth-store';

const user = { id: 'u1', name: 'Ada', email: 'ada@example.com', isGuest: false, isAdmin: false, createdAt: '', lastSeenAt: '' };

function mockApi(expiresIn = 86400) {
    const calls: string[] = [];
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
        calls.push(url);
        const body = url.includes('/api/auth/me')
            ? { user, quota: { tokensRemaining: 7, bucketCapacity: 25, resetsAt: '2026-01-01T00:00:00Z' } }
            : { expiresIn, user, quotaRemaining: 7, bucketCapacity: 25 };
        return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }) as typeof fetch;
    return calls;
}

describe('auth store session refresh (R2-LOG-11)', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null });
    });
    afterEach(() => {
        useAuthStore.getState().logout();
        vi.restoreAllMocks();
    });

    it('refreshes a session with two hours left exactly once on init', async () => {
        const twoHours = 2 * 60 * 60;
        localStorage.setItem('nexusagent_session_expires', String(Date.now() + twoHours * 1000));
        localStorage.setItem('nexusagent_user', JSON.stringify(user));
        const calls = mockApi(86400);

        await useAuthStore.getState().initAuth();

        expect(calls.filter((url) => url.includes('/api/auth/refresh'))).toHaveLength(1);
        expect(useAuthStore.getState().user).toEqual(user);
        const storedExpires = Number(localStorage.getItem('nexusagent_session_expires'));
        expect(storedExpires).toBeGreaterThan(Date.now() + 80000 * 1000);
    });

    it('leaves a session with plenty of time left alone', async () => {
        const twentyHours = 20 * 60 * 60;
        localStorage.setItem('nexusagent_session_expires', String(Date.now() + twentyHours * 1000));
        localStorage.setItem('nexusagent_user', JSON.stringify(user));
        const calls = mockApi(86400);

        await useAuthStore.getState().initAuth();

        expect(calls.some((url) => url.includes('/api/auth/refresh'))).toBe(false);
        expect(useAuthStore.getState().user).toEqual(user);
    });

    it('clearing the session wipes cached chats (logout on a shared device)', () => {
        localStorage.setItem('nexusagent_session_expires', '123456');
        localStorage.setItem('nexusagent_msgs_abc', '[]');
        localStorage.setItem('nexusagent_chat_history_u1', '[]');
        useAuthStore.setState({ user });
        mockApi(86400);

        useAuthStore.getState().logout();

        expect(localStorage.getItem('nexusagent_msgs_abc')).toBeNull();
        expect(localStorage.getItem('nexusagent_chat_history_u1')).toBeNull();
        expect(localStorage.getItem('nexusagent_session_expires')).toBeNull();
        expect(useAuthStore.getState().user).toBeNull();
    });
});

describe('session notice (R2-UX-02)', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null, sessionNotice: null });
    });

    it('explains an expired session after a 401 and clears on the next sign-in', async () => {
        useAuthStore.setState({ user });
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            statusText: 'Unauthorized',
            json: async () => ({ detail: 'Token has expired' })
        } as unknown as Response);
        const { apiClient } = await import('./api-client');

        await expect(apiClient('/api/auth/me')).rejects.toThrow();

        expect(useAuthStore.getState().user).toBeNull();
        expect(useAuthStore.getState().sessionNotice).toMatch(/session expired/i);

        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ expiresIn: 86400, user, quotaRemaining: 5, bucketCapacity: 5 })
        } as unknown as Response);
        await useAuthStore.getState().loginGuest();
        expect(useAuthStore.getState().sessionNotice).toBeNull();
        useAuthStore.getState().logout();
    });

    it('does not show the notice on a manual logout', () => {
        global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) } as unknown as Response);
        useAuthStore.setState({ user });

        useAuthStore.getState().logout();

        expect(useAuthStore.getState().sessionNotice).toBeNull();
    });
});

describe('guest device id (R2-SEC-11)', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null, sessionNotice: null });
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    async function guestDeviceId(): Promise<unknown> {
        let sent: { deviceId?: string } = {};
        global.fetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
            sent = JSON.parse(typeof init?.body === 'string' ? init.body : '{}');
            return {
                ok: true,
                status: 200,
                json: async () => ({ expiresIn: 86400, user, quotaRemaining: 5, bucketCapacity: 5 })
            } as unknown as Response;
        }) as typeof fetch;
        await useAuthStore.getState().loginGuest();
        const deviceId = sent.deviceId; // logout() below also calls fetch
        useAuthStore.getState().logout();
        return deviceId;
    }

    it('falls back to crypto.getRandomValues when randomUUID is missing', async () => {
        vi.stubGlobal('crypto', {
            getRandomValues: (bytes: Uint8Array) => {
                bytes.fill(0xab);
                return bytes;
            }
        });
        expect(await guestDeviceId()).toBe('ab'.repeat(16));
    });

    it('sends no device id when there is no secure RNG, so the server generates one', async () => {
        vi.stubGlobal('crypto', {});
        expect(await guestDeviceId()).toBeUndefined();
    });
});
