export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let authTokenGetter: () => string | null = () => {
    if (typeof window === 'undefined') return null;
    try {
        return localStorage.getItem('nexusagent_token');
    } catch {
        return null;
    }
};

let onUnauthorizedCallback: (() => void) | null = null;

export function setAuthTokenGetter(getter: () => string | null): void {
    authTokenGetter = getter;
}

export function setOnUnauthorizedCallback(callback: () => void): void {
    onUnauthorizedCallback = callback;
}

export interface ApiClientOptions extends RequestInit {
    params?: Record<string, string | number | boolean | undefined>;
    timeoutMs?: number;
}

export async function apiClient<T>(endpoint: string, options: ApiClientOptions = {}): Promise<T> {
    const token = authTokenGetter();
    const headers = new Headers(options.headers || {});

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }

    if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    let url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    if (options.params) {
        const parsedUrl = new URL(url, 'http://localhost');
        for (const [k, v] of Object.entries(options.params)) {
            if (v !== undefined) {
                parsedUrl.searchParams.set(k, String(v));
            }
        }
        url = endpoint.startsWith('http') ? parsedUrl.toString() : `${API_BASE}${parsedUrl.pathname}${parsedUrl.search}`;
    }

    const { params: _params, timeoutMs = 15000, ...fetchOptions } = options;

    let timeoutController: AbortController | null = null;
    let signal = fetchOptions.signal;

    if (!signal && typeof AbortController !== 'undefined') {
        timeoutController = new AbortController();
        signal = timeoutController.signal;
    }

    const timer = timeoutController ? setTimeout(() => timeoutController?.abort(), timeoutMs) : null;

    try {
        const response = await fetch(url, { ...fetchOptions, headers, signal });

        if (!response.ok) {
            if (response.status === 401) {
                onUnauthorizedCallback?.();
            }
            const errorData = await response.json().catch(() => null);

            let errorDetail: string | undefined;
            if (Array.isArray(errorData?.detail)) {
                errorDetail = errorData.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
            } else if (typeof errorData?.detail === 'string') {
                errorDetail = errorData.detail;
            } else if (typeof errorData?.message === 'string') {
                errorDetail = errorData.message;
            }

            throw new Error(errorDetail || `API error: ${response.statusText} (${response.status})`);
        }

        return (await response.json()) as T;
    } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
            throw new Error('Request timed out. Please check your network connection.');
        }
        throw err;
    } finally {
        if (timer) clearTimeout(timer);
    }
}
