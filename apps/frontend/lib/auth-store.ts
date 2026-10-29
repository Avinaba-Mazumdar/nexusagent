import { create } from 'zustand';
import type { UserSession, GuestPassResponse, TokenResponse } from '@nexusagent/contracts';
import { apiClient, setAuthTokenGetter, setOnUnauthorizedCallback } from './api-client';

const STORAGE_KEY_TOKEN = 'nexusagent_token';
const STORAGE_KEY_USER = 'nexusagent_user';
const STORAGE_KEY_QUOTA = 'nexusagent_quota';
const STORAGE_KEY_DEVICE_ID = 'nexusagent_device_id';
const CHAT_CACHE_PREFIXES = ['nexusagent_chat_history_', 'nexusagent_msgs_'];

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

function getOrCreateDeviceId(): string {
    if (typeof window === 'undefined') return '';
    try {
        let deviceId = localStorage.getItem(STORAGE_KEY_DEVICE_ID);
        if (!deviceId) {
            deviceId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 18);
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
    setIsGoogleLoading: (loading: boolean) => void;
    loginGuest: () => Promise<boolean>;
    loginGoogle: (credential: string) => Promise<boolean>;
    logout: () => void;
    setQuotaRemaining: (quota: number, resetsAt?: string | null) => void;
    initAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
    /** Forget the session locally (no server call: used when the server already rejected it). */
    function clearSession() {
        if (typeof window !== 'undefined') {
            try {
                localStorage.removeItem(STORAGE_KEY_TOKEN);
                localStorage.removeItem(STORAGE_KEY_USER);
                localStorage.removeItem(STORAGE_KEY_QUOTA);
                // Cached chat lists and transcripts must not outlive the session on a shared device.
                Object.keys(localStorage)
                    .filter((key) => CHAT_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix)))
                    .forEach((key) => localStorage.removeItem(key));
            } catch {
                // Storage unavailable
            }
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
        clearSession();
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
            error: null
        });
    };

    return {
        user: null,
        token: null,
        quotaRemaining: NO_QUOTA.remaining,
        bucketCapacity: NO_QUOTA.capacity,
        quotaResetsAt: null,
        isGuestLoading: false,
        isGoogleLoading: false,
        error: null,

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
