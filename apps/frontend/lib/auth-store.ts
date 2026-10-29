import { create } from 'zustand';
import type { UserSession, GuestPassResponse, TokenResponse } from '@nexusagent/contracts';
import { apiClient, getCookie, setCookie, removeCookie, setAuthTokenGetter, setOnUnauthorizedCallback } from './api-client';

const STORAGE_KEY_TOKEN = 'nexusagent_token';
const STORAGE_KEY_USER = 'nexusagent_user';
const STORAGE_KEY_QUOTA = 'nexusagent_quota';
const STORAGE_KEY_DEVICE_ID = 'nexusagent_device_id';
const CHAT_CACHE_PREFIXES = ['nexusagent_chat_history_', 'nexusagent_msgs_'];

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
    isLoading: boolean;
    isGuestLoading: boolean;
    isGoogleLoading: boolean;
    error: string | null;
    setIsGoogleLoading: (loading: boolean) => void;
    loginGuest: () => Promise<boolean>;
    loginGoogle: (credential: string) => Promise<boolean>;
    logout: () => void;
    setQuotaRemaining: (quota: number) => void;
    initAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
    // Register token getter with apiClient so every outbound fetch automatically attaches Authorization header
    setAuthTokenGetter(() => get().token);

    // Register 401 callback to smoothly reset session if server revokes or expires JWT token
    setOnUnauthorizedCallback(() => {
        get().logout();
    });

    return {
        user: null,
        token: null,
        quotaRemaining: 5,
        bucketCapacity: 5,
        isLoading: false,
        isGuestLoading: false,
        isGoogleLoading: false,
        error: null,

        setIsGoogleLoading: (loading: boolean) => {
            set({ isGoogleLoading: loading });
        },

        setQuotaRemaining: (quota: number) => {
            if (typeof window !== 'undefined') {
                localStorage.setItem(STORAGE_KEY_QUOTA, quota.toString());
            }
            set({ quotaRemaining: quota });
        },

        initAuth: async () => {
            if (typeof window === 'undefined') return;
            try {
                localStorage.removeItem('nexusagent_byok_key');
                localStorage.removeItem('nexusagent_byok_provider');

                const token = localStorage.getItem(STORAGE_KEY_TOKEN) || getCookie(STORAGE_KEY_TOKEN);
                const userStr = localStorage.getItem(STORAGE_KEY_USER);
                const quota = localStorage.getItem(STORAGE_KEY_QUOTA);

                if (!token || !userStr) {
                    return;
                }

                const user = JSON.parse(userStr) as UserSession;
                set({
                    token,
                    user,
                    quotaRemaining: quota ? parseInt(quota, 10) : 5
                });

                // Server-side session validation against Neon PostgreSQL via API client
                try {
                    const data = await apiClient<{
                        user: UserSession;
                        quota?: { tokensRemaining: number; bucketCapacity: number };
                    }>('/api/auth/me');

                    const validatedUser = data.user;
                    const validatedQuota = data.quota?.tokensRemaining ?? 5;
                    const validatedCapacity = data.quota?.bucketCapacity ?? 5;

                    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(validatedUser));
                    localStorage.setItem(STORAGE_KEY_QUOTA, validatedQuota.toString());
                    setCookie(STORAGE_KEY_TOKEN, token);

                    set({
                        user: validatedUser,
                        quotaRemaining: validatedQuota,
                        bucketCapacity: validatedCapacity
                    });
                } catch {
                    // Handled by 401 interceptor or offline resilience
                }
            } catch {
                get().logout();
            }
        },

        loginGuest: async () => {
            set({ isGuestLoading: true, isLoading: true, error: null });
            try {
                const deviceId = getOrCreateDeviceId();
                const data = await apiClient<GuestPassResponse>('/api/auth/guest', {
                    method: 'POST',
                    body: JSON.stringify({ deviceId: deviceId || undefined })
                });

                const token = data.tokens.accessToken;
                const user = data.user;
                const quotaRemaining = data.quotaRemaining;
                const bucketCapacity = data.bucketCapacity;

                if (typeof window !== 'undefined') {
                    localStorage.setItem(STORAGE_KEY_TOKEN, token);
                    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
                    localStorage.setItem(STORAGE_KEY_QUOTA, quotaRemaining.toString());
                    setCookie(STORAGE_KEY_TOKEN, token);
                }

                set({
                    token,
                    user,
                    quotaRemaining,
                    bucketCapacity,
                    isGuestLoading: false,
                    isLoading: false,
                    error: null
                });
                return true;
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Unknown error during guest sign-in';
                set({ isGuestLoading: false, isLoading: false, error: message });
                return false;
            }
        },

        loginGoogle: async (credential: string) => {
            set({ isGoogleLoading: true, isLoading: true, error: null });
            try {
                const data = await apiClient<TokenResponse>('/api/auth/google', {
                    method: 'POST',
                    body: JSON.stringify({ credential })
                });

                const token = data.accessToken;
                const user = data.user;
                const quotaRemaining = data.quotaRemaining ?? 25;
                const bucketCapacity = data.bucketCapacity ?? 25;

                if (typeof window !== 'undefined') {
                    localStorage.setItem(STORAGE_KEY_TOKEN, token);
                    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
                    localStorage.setItem(STORAGE_KEY_QUOTA, quotaRemaining.toString());
                    setCookie(STORAGE_KEY_TOKEN, token);
                }

                set({
                    token,
                    user,
                    quotaRemaining,
                    bucketCapacity,
                    isGoogleLoading: false,
                    isLoading: false,
                    error: null
                });
                return true;
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Unknown error during Google sign-in';
                set({ isGoogleLoading: false, isLoading: false, error: message });
                return false;
            }
        },
        logout: () => {
            if (typeof window !== 'undefined') {
                localStorage.removeItem(STORAGE_KEY_TOKEN);
                localStorage.removeItem(STORAGE_KEY_USER);
                localStorage.removeItem(STORAGE_KEY_QUOTA);
                localStorage.removeItem('nexusagent_byok_key');
                localStorage.removeItem('nexusagent_byok_provider');
                removeCookie(STORAGE_KEY_TOKEN);
                // Cached chat lists and transcripts must not outlive the session on a shared device.
                Object.keys(localStorage)
                    .filter((key) => CHAT_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix)))
                    .forEach((key) => localStorage.removeItem(key));
            }
            set({
                user: null,
                token: null,
                quotaRemaining: 5,
                bucketCapacity: 5,
                isGuestLoading: false,
                isGoogleLoading: false,
                isLoading: false,
                error: null
            });
        }
    };
});
