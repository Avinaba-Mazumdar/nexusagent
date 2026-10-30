export interface SecurityHeaderOptions {
    isProduction: boolean;
    /** Opt in to `includeSubDomains; preload` (a commitment for the whole registrable domain). */
    hstsPreload: boolean;
}

export interface HeaderEntry {
    key: string;
    value: string;
}

/** Static response headers. The Content-Security-Policy is set per request in proxy.ts (it needs a nonce). */
export function buildSecurityHeaders({ isProduction, hstsPreload }: SecurityHeaderOptions): HeaderEntry[] {
    const headers: HeaderEntry[] = [
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' }
    ];
    if (isProduction) {
        headers.push({
            key: 'Strict-Transport-Security',
            value: hstsPreload ? 'max-age=63072000; includeSubDomains; preload' : 'max-age=31536000'
        });
    }
    return headers;
}
