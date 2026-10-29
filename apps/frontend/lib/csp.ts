export interface CspOptions {
    nonce: string;
    isDev: boolean;
    /** Origin of the backend API (from NEXT_PUBLIC_API_URL), if any. */
    apiOrigin: string;
}

export function apiOriginFromEnv(apiUrl: string | undefined): string {
    if (!apiUrl) return '';
    try {
        return new URL(apiUrl).origin;
    } catch {
        return '';
    }
}

/**
 * Content-Security-Policy for one response.
 * Scripts need the per-request nonce ('strict-dynamic' lets Next.js and Google Sign-In load their own
 * scripts); there is no 'unsafe-inline' for scripts. Styles still allow inline because Radix UI and the
 * Google button set inline style attributes.
 */
export function buildCsp({ nonce, isDev, apiOrigin }: CspOptions): string {
    const connectSrc = ["'self'", apiOrigin, 'https://accounts.google.com', ...(isDev ? ['http://localhost:*', 'http://127.0.0.1:*', 'ws://localhost:*'] : [])].filter(Boolean);
    const scriptSrc = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...(isDev ? ["'unsafe-eval'"] : []), 'https://accounts.google.com', 'https://apis.google.com'];

    return [
        `default-src 'self'`,
        `script-src ${scriptSrc.join(' ')}`,
        `style-src 'self' 'unsafe-inline' https://accounts.google.com`,
        `img-src 'self' data: blob: https://lh3.googleusercontent.com https://accounts.google.com`,
        `font-src 'self' data:`,
        `object-src 'none'`,
        `base-uri 'self'`,
        `form-action 'self'`,
        `frame-ancestors 'none'`,
        `frame-src 'self' https://accounts.google.com`,
        `connect-src ${connectSrc.join(' ')}`,
        ...(isDev ? [] : ['upgrade-insecure-requests'])
    ].join('; ');
}
