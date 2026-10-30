import { create } from 'zustand';
import type { UserSession, GuestPassResponse, TokenResponse } from '@nexusagent/contracts';
import { apiClient, setAuthTokenGetter, setOnUnauthorizedCallback } from './api-client';
import { clearChatCache } from './chat-cache';

const STORAGE_KEY_TOKEN = 'nexusagent_token';
const STORAGE_KEY_USER = 'nexusagent_user';
const STORAGE_KEY_QUOTA = 'nexusagent_quota';
const STORAGE_KEY_DEVICE_ID = 'nexusagent_device_id';
/** Renew the token when less than this is left (tokens last 24 h), and re-check this often while the tab is open. */
const SESSION_EXPIRED_NOTICE = 'Your session expired. Please sign in again.';
const REFRESH_WHEN_LEFT_SECONDS = 12 * 60 * 60;
const REFRESH_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;

/** Seconds until the JWT's `exp`, or null when the token cannot be read. */
function secondsUntilExpiry(token: string): number | null {
    try {
        const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const exp = (JSON.parse(atob(payload)) as { exp?: unknown }).exp;
        return typeof exp === 'number' ? exp - Date.now() / 1000 : null;
    } catch {
        return null;
    }
}

/** Quota numbers always come from the server; these are only shown until it answers. */
interface QuotaSnapshot {
    remaining: number;
    capacity: number;
    resetsAt: string | null;
}

const NO_QUOTA: QuotaSnapshot = { remaining: 0, capacity: 0, resetsAt: null };

function readCachedQuota(): QuotaSnapshot {
    try {
        const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY_QUOTA) ?? 'null');
        if (typeof parsed?.remaining === 'number' && typeof parsed?.capacity === 'number') {
            return { remaining: parsed.remaining, capacity: parsed.capacity, resetsAt: parsed.resetsAt ?? null };
        }
    } catch {
        // Corrupt cache: fall through
    }
    return NO_QUOTA;
}

/** A random, unguessable id; empty when no secure RNG exists, so the server generates one instead. */
function newDeviceId(): string {
    if (typeof crypto === 'undefined') return '';
    if (crypto.randomUUID) return crypto.randomUUID();
    if (crypto.getRandomValues) {
        return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('');
    }
    return '';
}

function getOrCreateDeviceId(): string {
    if (typeof window === 'undefined') return '';
    try {
        let deviceId = localStorage.getItem(STORAGE_KEY_DEVICE_ID);
        if (!deviceId) {
            deviceId = newDeviceId();
            if (!deviceId) return '';
            localStorage.setItem(STORAGE_KEY_DEVICE_ID, deviceId);
        }
        return deviceId;
    } catch {
        return '';
    }
}

interface AuthState {
    user: UserSession | null;
    token: string | null;
    quotaRemaining: number;
    bucketCapacity: number;
    /** ISO time when the bucket refills, if the server told us. */
    quotaResetsAt: string | null;
    isGuestLoading: boolean;
    isGoogleLoading: boolean;
    error: string | null;
    /** Set when the server ended the session (expired or revoked); cleared by the next sign-in. */
    sessionNotice: string | null;
    setIsGoogleLoading: (loading: boolean) => void;
    loginGuest: () => Promise<boolean>;
    loginGoogle: (credential: string) => Promise<boolean>;
    logout: () => void;
    setQuotaRemaining: (quota: number, resetsAt?: string | null) => void;
    initAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
    let refreshTimer: ReturnType<typeof setInterval> | null = null;

    /** Forget the session locally (no server call: used when the server already rejected it). */
    function clearSession() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
        if (typeof window !== 'undefined') {
            try {
                localStorage.removeItem(STORAGE_KEY_TOKEN);
                localStorage.removeItem(STORAGE_KEY_USER);
                localStorage.removeItem(STORAGE_KEY_QUOTA);
            } catch {
                // Storage unavailable
            }
            clearChatCache();
        }
        set({
            user: null,
            token: null,
            quotaRemaining: NO_QUOTA.remaining,
            bucketCapacity: NO_QUOTA.capacity,
            quotaResetsAt: null,
            isGuestLoading: false,
            isGoogleLoading: false,
            error: null
        });
    }

    // Register token getter with apiClient so every outbound fetch automatically attaches Authorization header
    setAuthTokenGetter(() => get().token);

    // Register 401 callback to smoothly reset session if server revokes or expires JWT token
    setOnUnauthorizedCallback(() => {
        const hadSession = Boolean(get().token);
        clearSession();
        if (hadSession) set({ sessionNotice: SESSION_EXPIRED_NOTICE });
    });

    const persistQuota = (quota: QuotaSnapshot) => {
        try {
            localStorage.setItem(STORAGE_KEY_QUOTA, JSON.stringify(quota));
        } catch {
            // Storage unavailable: the in-memory value still works for this tab.
        }
    };

    /** Single place that records a login: persists the session and updates the store. */
    const applySession = (token: string, user: UserSession, quota: QuotaSnapshot) => {
        try {
            localStorage.setItem(STORAGE_KEY_TOKEN, token);
            localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
        } catch {
            // Storage unavailable: session lasts until the tab closes.
        }
        persistQuota(quota);
        set({
            token,
            user,
            quotaRemaining: quota.remaining,
            bucketCapacity: quota.capacity,
            quotaResetsAt: quota.resetsAt,
            isGuestLoading: false,
            isGoogleLoading: false,
            error: null,
            sessionNotice: null
        });
        startRefreshTimer();
    };

    /** Swap the token for a fresh one when it is close to expiring. Failures are ignored: the 401 path handles a dead session. */
    async function refreshSessionIfNeeded() {
        const { token, user } = get();
        if (!token || !user) return;
        const left = secondsUntilExpiry(token);
        if (left === null || left > REFRESH_WHEN_LEFT_SECONDS) return;
        try {
            const data = await apiClient<TokenResponse>('/api/auth/refresh', { method: 'POST' });
            applySession(data.accessToken, data.user, {
                remaining: data.quotaRemaining ?? get().quotaRemaining,
                capacity: data.bucketCapacity ?? get().bucketCapacity,
                resetsAt: get().quotaResetsAt
            });
        } catch {
            // Keep the current token.
        }
    }

    function startRefreshTimer() {
        if (refreshTimer) return;
        refreshTimer = setInterval(() => void refreshSessionIfNeeded(), REFRESH_CHECK_INTERVAL_MS);
    }

    return {
        user: null,
        token: null,
        quotaRemaining: NO_QUOTA.remaining,
        bucketCapacity: NO_QUOTA.capacity,
        quotaResetsAt: null,
        isGuestLoading: false,
        isGoogleLoading: false,
        error: null,
        sessionNotice: null,

        setIsGoogleLoading: (loading: boolean) => {
            set({ isGoogleLoading: loading });
        },

        setQuotaRemaining: (quota: number, resetsAt?: string | null) => {
            const next = { remaining: quota, capacity: get().bucketCapacity, resetsAt: resetsAt === undefined ? get().quotaResetsAt : resetsAt };
            persistQuota(next);
            set({ quotaRemaining: next.remaining, quotaResetsAt: next.resetsAt });
        },

        initAuth: async () => {
            if (typeof window === 'undefined') return;
            try {
                const token = localStorage.getItem(STORAGE_KEY_TOKEN);
                const userStr = localStorage.getItem(STORAGE_KEY_USER);
                if (!token || !userStr) {
                    return;
                }

                const cached = readCachedQuota();
                set({
                    token,
                    user: JSON.parse(userStr) as UserSession,
                    quotaRemaining: cached.remaining,
                    bucketCapacity: cached.capacity,
                    quotaResetsAt: cached.resetsAt
                });

                // Server-side session validation via the API client
                try {
                    const data = await apiClient<{
                        user: UserSession;
                        quota: { tokensRemaining: number; bucketCapacity: number; resetsAt?: string };
                    }>('/api/auth/me');
                    applySession(token, data.user, {
                        remaining: data.quota.tokensRemaining,
                        capacity: data.quota.bucketCapacity,
                        resetsAt: data.quota.resetsAt ?? null
                    });
                    await refreshSessionIfNeeded();
                } catch {
                    // Handled by 401 interceptor or offline resilience
                }
            } catch {
                clearSession();
            }
        },

        loginGuest: async () => {
            set({ isGuestLoading: true, error: null });
            try {
                const deviceId = getOrCreateDeviceId();
                const data = await apiClient<GuestPassResponse>('/api/auth/guest', {
                    method: 'POST',
                    body: JSON.stringify({ deviceId: deviceId || undefined })
                });
                applySession(data.tokens.accessToken, data.user, { remaining: data.quotaRemaining, capacity: data.bucketCapacity, resetsAt: null });
                return true;
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Unknown error during guest sign-in';
                set({ isGuestLoading: false, error: message });
                return false;
            }
        },

        loginGoogle: async (credential: string) => {
            set({ isGoogleLoading: true, error: null });
            try {
                const data = await apiClient<TokenResponse>('/api/auth/google', {
                    method: 'POST',
                    body: JSON.stringify({ credential })
                });
                applySession(data.accessToken, data.user, {
                    remaining: data.quotaRemaining ?? 0,
                    capacity: data.bucketCapacity ?? 0,
                    resetsAt: null
                });
                return true;
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Unknown error during Google sign-in';
                set({ isGoogleLoading: false, error: message });
                return false;
            }
        },

        logout: () => {
            // Revoke the token server-side (fire and forget), then forget it locally.
            if (get().token) void apiClient('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
            clearSession();
        }
    };
});
